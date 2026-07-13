#!/usr/bin/env python3
"""LLM + solver end-to-end harness (#106). Manual, non-deterministic — NOT CI.

Reproduces docs/llm-interaction.md with a REAL model: the LLM gets the courier
problem in natural language plus tools — a local ``write_file`` and the pddlpy
MCP server's ``validate``/``ground``/``solve``/``parse`` (served by
``uvx --from "pddlpy[mcp]" pddlpy-mcp``, i.e. the *published* package in a
transient environment, per the issue). The conversation is captured to a
markdown transcript; soundness checks assert the solver found the 7-toll plan
and the final answer mentions it.

Usage:
    export OPENROUTER_API_KEY=...
    uv run --with mcp,httpx python e2e/llm/harness.py --model qwen/qwen-2.5-72b-instruct
    uv run --with mcp,httpx python e2e/llm/harness.py --dry-run   # no API key: replays
                                                                  # the doc's scripted turns
                                                                  # to exercise the pipeline

Exit codes: 0 sound, 1 conversation finished but unsound, 2 harness/setup error.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import pathlib
import re
import sys
import tempfile

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = pathlib.Path(__file__).parent
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

PROBLEM = """\
A courier is at the depot and must deliver a parcel to town, spending as
little as possible on tolls. The direct highway costs 10. There's a route
through the junction: 5 to get there, then 6 into town. And there's a
back-road chain: riverside (2), then the old bridge (2), then into town (3).
Roads are one-way. What's the cheapest route?"""

SYSTEM = """\
You are a planning assistant with tools. Do not compute the plan yourself —
your arithmetic is not a proof. Instead:
1. Translate the user's problem into classical planning PDDL: a domain file
   and a problem file with action costs (:action-costs, total-cost) and a
   (:metric minimize (total-cost)). Use write_file to save them.
2. Call validate on the two files and fix any reported issue.
3. Call solve with planner "ucs" (cost-optimal).
4. Answer the user in plain language: the cheapest route and its total cost,
   based ONLY on the solver's output.

PDDL action-costs syntax reminder: declare `(:functions (total-cost) (toll
?a - place ?b - place))` in the domain; the action effect uses `(increase
(total-cost) (toll ?from ?to))`; the problem's :init sets `(= (toll a b) 5)`
and `(= (total-cost) 0)`; end the problem with
`(:metric minimize (total-cost))`. There is no `:cost` field."""


def mcp_tools_to_openai(tools) -> list:
    """Convert MCP tool declarations to OpenAI/OpenRouter function schemas."""
    out = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        })
    return out


WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write a text file (e.g. domain.pddl / problem.pddl) into "
                       "the working directory. Returns the absolute path to pass "
                       "to the other tools.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Base name, e.g. domain.pddl"},
                "content": {"type": "string"},
            },
            "required": ["filename", "content"],
        },
    },
}


class Conversation:
    """Message log + markdown rendering."""

    def __init__(self) -> None:
        self.messages: list = [{"role": "system", "content": SYSTEM},
                               {"role": "user", "content": PROBLEM}]
        self.tool_results: list = []   # (name, arguments, result_text)

    def to_markdown(self, model: str) -> str:
        lines = [f"# LLM + pddlpy end-to-end transcript",
                 f"", f"- **model:** `{model}`",
                 f"- **captured:** {datetime.date.today().isoformat()}", ""]
        for m in self.messages:
            role = m["role"]
            if role == "system":
                lines += ["## System prompt", "", "```", m["content"], "```", ""]
            elif role == "user":
                lines += ["## User", "", m["content"], ""]
            elif role == "assistant":
                if m.get("content"):
                    lines += ["## Assistant", "", m["content"], ""]
                for tc in m.get("tool_calls") or []:
                    fn = tc["function"]
                    lines += [f"### Tool call: `{fn['name']}`", "", "```json",
                              fn["arguments"], "```", ""]
            elif role == "tool":
                lines += ["### Tool result", "", "```json", m["content"], "```", ""]
        return "\n".join(lines)


async def run_tool(session: ClientSession, workdir: pathlib.Path,
                   name: str, args: dict) -> str:
    """Execute one tool call (local write_file or MCP) and return result text."""
    if name == "write_file":
        base = os.path.basename(args["filename"])
        content = args["content"]
        # Weaker models double-escape newlines inside JSON tool arguments;
        # if the "file" is one line full of literal \n sequences, decode them.
        if "\n" not in content and "\\n" in content:
            content = content.replace("\\n", "\n").replace("\\t", "\t")
        path = workdir / base
        path.write_text(content, encoding="utf-8")
        return json.dumps({"path": str(path)})
    result = await session.call_tool(name, args)
    if result.structuredContent is not None:
        return json.dumps(result.structuredContent.get("result", result.structuredContent))
    return "".join(c.text for c in result.content if getattr(c, "text", None))


async def chat_round(client: httpx.AsyncClient, model: str, messages: list,
                     tools: list) -> dict:
    r = await client.post(
        OPENROUTER_URL,
        headers={"Authorization": "Bearer %s" % os.environ["OPENROUTER_API_KEY"]},
        json={"model": model, "messages": messages, "tools": tools},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


def dry_run_turns(workdir: pathlib.Path) -> list:
    """Scripted assistant turns (the doc's simulation) to exercise the whole
    pipeline — MCP server, tool dispatch, transcript, soundness — offline."""
    domain = (HERE / ".." / ".." / "examples" / "pddl" / "courier-domain.pddl").resolve()
    problem = (HERE / ".." / ".." / "examples" / "pddl" / "courier-problem.pddl").resolve()
    return [
        {"tool_calls": [
            ("write_file", {"filename": "domain.pddl", "content": domain.read_text()}),
            ("write_file", {"filename": "problem.pddl", "content": problem.read_text()}),
        ]},
        {"tool_calls": [
            ("validate", {"domain_file": str(workdir / "domain.pddl"),
                          "problem_file": str(workdir / "problem.pddl")}),
        ]},
        {"tool_calls": [
            ("solve", {"domain_file": str(workdir / "domain.pddl"),
                       "problem_file": str(workdir / "problem.pddl"),
                       "planner": "ucs"}),
        ]},
        {"content": "The cheapest delivery costs 7 tolls: depot -> riverside (2), "
                    "old bridge (2), then into town (3). The direct highway (10) "
                    "and the junction route (11) are both more expensive."},
    ]


def soundness(convo: Conversation) -> list:
    """Step-7 checks: solver reached the optimum and the answer reports it."""
    failures = []
    solved = [r for (n, a, r) in convo.tool_results if n == "solve"]
    if not any('"cost": 7.0' in r or "'cost': 7.0" in r for r in solved):
        failures.append("no solve result with cost 7.0")
    validated = [r for (n, a, r) in convo.tool_results if n == "validate"]
    if not validated:
        failures.append("validate was never called")
    final = next((m.get("content") or "" for m in reversed(convo.messages)
                  if m["role"] == "assistant"), "")
    if not re.search(r"\b7\b", final):
        failures.append("final answer does not state the cost 7")
    if not all(w in final.lower() for w in ("riverside", "bridge", "town")):
        failures.append("final answer does not narrate the optimal route")
    return failures


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen/qwen-2.5-72b-instruct")
    ap.add_argument("--server-cmd", default='uvx --from pddlpy[mcp] pddlpy-mcp',
                    help="MCP server command (default: published pddlpy via uvx)")
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true",
                    help="replay scripted turns; no API key needed")
    args = ap.parse_args()

    if not args.dry_run and "OPENROUTER_API_KEY" not in os.environ:
        print("OPENROUTER_API_KEY not set (use --dry-run to test the pipeline)",
              file=sys.stderr)
        return 2

    workdir = pathlib.Path(tempfile.mkdtemp(prefix="pddlpy-e2e-"))
    cmd, *cmd_args = args.server_cmd.split()
    params = StdioServerParameters(command=cmd, args=cmd_args)
    convo = Conversation()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            tools = mcp_tools_to_openai(mcp_tools) + [WRITE_FILE_TOOL]

            scripted = dry_run_turns(workdir) if args.dry_run else None
            async with httpx.AsyncClient() as http:
                for turn in range(args.max_turns):
                    if scripted is not None:
                        if not scripted:
                            break
                        step = scripted.pop(0)
                        msg = {"role": "assistant",
                               "content": step.get("content"),
                               "tool_calls": [
                                   {"id": "call_%d_%d" % (turn, i), "type": "function",
                                    "function": {"name": n, "arguments": json.dumps(a)}}
                                   for i, (n, a) in enumerate(step.get("tool_calls", []))
                               ] or None}
                    else:
                        msg = await chat_round(http, args.model, convo.messages, tools)
                    convo.messages.append(msg)
                    calls = msg.get("tool_calls") or []
                    if not calls:
                        break
                    for tc in calls:
                        fn = tc["function"]
                        # Small models emit malformed JSON arguments; answer
                        # with an error result instead of crashing the run.
                        try:
                            fargs = json.loads(fn["arguments"])
                            result = await run_tool(session, workdir,
                                                    fn["name"], fargs)
                            convo.tool_results.append((fn["name"], fargs, result))
                        except (json.JSONDecodeError, KeyError, TypeError) as exc:
                            result = ("Error: tool call arguments were not valid "
                                      "JSON (%s). Repeat the call with valid, "
                                      "complete JSON arguments." % exc)
                        convo.messages.append({"role": "tool",
                                               "tool_call_id": tc["id"],
                                               "content": result})

    label = "dry-run" if args.dry_run else args.model.replace("/", "_")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = HERE / "transcripts" / ("%s-%s.md" % (label, stamp))
    out.write_text(convo.to_markdown("dry-run" if args.dry_run else args.model),
                   encoding="utf-8")
    print("transcript: %s" % out)

    failures = soundness(convo)
    if failures:
        print("UNSOUND:", "; ".join(failures))
        return 1
    print("SOUND: solver optimum reached and narrated")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
