#!/usr/bin/env python3
"""LLM playground: scenarios x models x arms. Manual, non-deterministic, NOT CI.

Every arm sees the same English problem (scenarios/<name>/problem.md) and must
answer in English; only the tools differ:

    bare     no tools                           what the model learned in training
    python   run_python (sandboxed)             does it write a solver on its own
    pddlpy   write_file + pddlpy MCP tools      the pddl-lib route

The answer is graded against the scenario's reference PDDL (see grader.py).

    playground.py list                       scenarios and their optimum
    playground.py show courier               the English text a model sees
    playground.py check                      solve every reference problem
    playground.py run courier blocksworld --arm bare,python,pddlpy \\
        --model openai/gpt-5,qwen/qwen3-235b-a22b --repeats 3
    playground.py run courier --arm bare --dry-run   # canned replies, no API key
    playground.py grade courier answer.txt   # grade an answer by hand

Results land in e2e/llm/results/<stamp>/: results.md (table), results.jsonl,
and one markdown transcript per run. Models are OpenRouter ids
(OPENROUTER_API_KEY).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import datetime
import itertools
import json
import os
import pathlib
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

HERE = pathlib.Path(__file__).parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import grader  # noqa: E402
import sandbox  # noqa: E402
import scenarios  # noqa: E402

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
ARMS = ("bare", "python", "pddlpy")
DEFAULT_GRADER = "openai/gpt-5-mini"

# Deliberately neutral: say which tools exist, never how to solve the problem.
SYSTEM = {
    "bare": None,
    "python": "You can run Python programs with the run_python tool.",
    "pddlpy": "You have a PDDL planner. Use write_file to save PDDL domain and "
              "problem files, and the pddlpy tools (validate, solve, ...) on them.",
}

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


# -- model access -------------------------------------------------------------

class OpenRouter:
    def __init__(self, http) -> None:
        self.http = http
        self.key = os.environ["OPENROUTER_API_KEY"]

    async def chat(self, model: str, messages: list, tools: Optional[list] = None,
                   **extra) -> dict:
        body: Dict[str, Any] = {"model": model, "messages": messages, **extra}
        if tools:
            body["tools"] = tools
        for attempt in range(4):
            r = await self.http.post(
                OPENROUTER_URL, json=body, timeout=600,
                headers={"Authorization": "Bearer %s" % self.key})
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                await asyncio.sleep(5 * 2 ** attempt)
                continue
            r.raise_for_status()
            data = r.json()
            if "choices" not in data:
                raise RuntimeError("OpenRouter: %s" % data.get("error", data))
            return data
        raise AssertionError("unreachable")


# -- one run ----------------------------------------------------------------

@dataclass
class Run:
    scenario: str
    arm: str
    model: str
    rep: int
    verdict: str = ""
    cost: Optional[float] = None
    optimum: Optional[float] = None
    turns: int = 0
    tool_calls: Dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0
    tokens: int = 0
    detail: str = ""
    transcript: str = ""


def _attr(obj, *names):
    """mcp 2.x uses snake_case fields, 1.x camelCase."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return None


def tool_list(arm: str, mcp_tools) -> list:
    if arm == "python":
        return [sandbox.TOOL]
    if arm == "pddlpy":
        return [{"type": "function", "function": {
            "name": t.name, "description": t.description or "",
            "parameters": _attr(t, "input_schema", "inputSchema")}}
            for t in mcp_tools] + [WRITE_FILE_TOOL]
    return []


async def call_tool(name: str, args: dict, workdir: pathlib.Path, session, n: int) -> str:
    if name == "run_python":
        return await asyncio.to_thread(sandbox.run_python, args["code"], workdir, 60.0, n)
    if name == "write_file":
        content = args["content"]
        # Weaker models double-escape newlines inside JSON tool arguments.
        if "\n" not in content and "\\n" in content:
            content = content.replace("\\n", "\n").replace("\\t", "\t")
        path = workdir / os.path.basename(args["filename"])
        path.write_text(content, encoding="utf-8")
        return json.dumps({"path": str(path)})
    if session is None:
        return "Error: unknown tool %r" % name
    result = await session.call_tool(name, args)
    structured = _attr(result, "structured_content", "structuredContent")
    if structured is not None:
        return json.dumps(structured.get("result", structured))
    return "".join(c.text for c in result.content if getattr(c, "text", None))


def dry_run_turns(sc: scenarios.Scenario, arm: str, workdir: pathlib.Path) -> list:
    """Canned assistant turns: the reference plan, reached the arm's way."""
    plan = "\n".join(scenarios.check(sc).plan)
    answer = "Here is the plan:\n\n%s\n" % plan
    if arm == "python":
        return [{"tool_calls": [("run_python", {"code": "print(%r)" % plan})]},
                {"content": answer}]
    if arm == "pddlpy":
        d, p = str(workdir / "domain.pddl"), str(workdir / "problem.pddl")
        return [
            {"tool_calls": [
                ("write_file", {"filename": "domain.pddl",
                                "content": sc.domain_file.read_text()}),
                ("write_file", {"filename": "problem.pddl",
                                "content": sc.problem_file.read_text()})]},
            {"tool_calls": [("validate", {"domain_file": d, "problem_file": p})]},
            {"tool_calls": [("solve", {"domain_file": d, "problem_file": p,
                                       "planner": sc.planner})]},
            {"content": answer}]
    return [{"content": answer}]


def scripted_message(step: dict, turn: int) -> dict:
    calls = [{"id": "call_%d_%d" % (turn, i), "type": "function",
              "function": {"name": n, "arguments": json.dumps(a)}}
             for i, (n, a) in enumerate(step.get("tool_calls", []))]
    return {"role": "assistant", "content": step.get("content"),
            "tool_calls": calls or None}


async def converse(run: Run, sc, client, session, mcp_tools, max_turns: int,
                   dry_run: bool) -> List[dict]:
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="pddlpy-play-"))
    messages: List[dict] = []
    if SYSTEM[run.arm]:
        messages.append({"role": "system", "content": SYSTEM[run.arm]})
    messages.append({"role": "user", "content": sc.text})
    tools = tool_list(run.arm, mcp_tools)
    scripted = dry_run_turns(sc, run.arm, workdir) if dry_run else None
    n_calls = 0
    for turn in range(max_turns):
        if scripted is not None:
            if not scripted:
                break
            msg = scripted_message(scripted.pop(0), turn)
        else:
            data = await client.chat(run.model, messages, tools)
            run.tokens += (data.get("usage") or {}).get("total_tokens", 0)
            msg = data["choices"][0]["message"]
            msg = {k: msg.get(k) for k in ("role", "content", "tool_calls", "reasoning")
                   if msg.get(k) is not None}
            msg.setdefault("role", "assistant")
        messages.append(msg)
        run.turns += 1
        calls = msg.get("tool_calls") or []
        if not calls:
            break
        for tc in calls:
            fn = tc["function"]
            run.tool_calls[fn["name"]] = run.tool_calls.get(fn["name"], 0) + 1
            try:
                result = await call_tool(fn["name"], json.loads(fn["arguments"] or "{}"),
                                         workdir, session, n_calls)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                # Small models emit malformed arguments; answer, don't crash.
                result = ("Error: tool call arguments were not valid JSON (%s). "
                          "Repeat the call with valid, complete JSON arguments." % exc)
            n_calls += 1
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    else:
        run.detail = "stopped after %d turns" % max_turns
    return messages


def final_answer(messages: List[dict]) -> str:
    last = messages[-1] if messages else {}
    if last.get("role") != "assistant" or last.get("tool_calls"):
        return ""
    return last.get("content") or ""


def to_markdown(run: Run, messages: List[dict], g: grader.Grade) -> str:
    lines = ["# %s · %s · %s · rep %d" % (run.scenario, run.arm, run.model, run.rep), "",
             "- **verdict:** `%s`" % g.verdict,
             "- **cost / optimum:** %s / %s" % (g.cost, g.optimum),
             "- **turns:** %d, **tool calls:** %s, **tokens:** %d, **seconds:** %.0f"
             % (run.turns, run.tool_calls or "none", run.tokens, run.seconds)]
    if g.detail or run.detail:
        lines.append("- **detail:** %s" % "; ".join(x for x in (run.detail, g.detail) if x))
    lines += ["- **graded plan** (%s):" % (g.source or "-"), "", "```",
              "\n".join(g.steps) or "(none)", "```", ""]
    for m in messages:
        role = m["role"]
        if role == "system":
            lines += ["## System", "", m["content"], ""]
        elif role == "user":
            lines += ["## User", "", m["content"], ""]
        elif role == "assistant":
            if m.get("reasoning"):
                lines += ["<details><summary>reasoning</summary>", "", "```",
                          m["reasoning"], "```", "</details>", ""]
            if m.get("content"):
                lines += ["## Assistant", "", m["content"], ""]
            for tc in m.get("tool_calls") or []:
                fn = tc["function"]
                args = fn["arguments"]
                with contextlib.suppress(ValueError, TypeError):
                    parsed = json.loads(args)
                    if isinstance(parsed, dict) and len(parsed) == 1 and "code" in parsed:
                        lines += ["### `%s`" % fn["name"], "", "```python",
                                  parsed["code"], "```", ""]
                        continue
                    if isinstance(parsed, dict) and set(parsed) == {"filename", "content"}:
                        lines += ["### `%s` %s" % (fn["name"], parsed["filename"]), "",
                                  "```lisp", parsed["content"], "```", ""]
                        continue
                    args = json.dumps(parsed, indent=1)
                lines += ["### `%s`" % fn["name"], "", "```json", args, "```", ""]
        elif role == "tool":
            lines += ["### result", "", "```", m["content"], "```", ""]
    return "\n".join(lines)


async def one_run(run: Run, sc, client, grade_client, grader_model, session,
                  mcp_tools, max_turns, dry_run, outdir) -> Run:
    t0 = time.monotonic()
    try:
        messages = await converse(run, sc, client, session, mcp_tools, max_turns, dry_run)
    except Exception as exc:  # network / API errors: record and move on
        run.verdict, run.detail = "error", "%s: %s" % (type(exc).__name__, exc)
        run.seconds = time.monotonic() - t0
        return run
    run.seconds = time.monotonic() - t0
    answer = final_answer(messages)

    async def extract_async(prompt: str) -> str:
        data = await grade_client.chat(grader_model, [{"role": "user", "content": prompt}],
                                       temperature=0)
        return data["choices"][0]["message"].get("content") or ""

    extractor = None
    if grade_client is not None and answer:
        loop = asyncio.get_running_loop()

        def extractor(prompt: str) -> str:
            return asyncio.run_coroutine_threadsafe(extract_async(prompt), loop).result()

    try:
        g = await asyncio.to_thread(grader.grade, sc, answer, extractor)
    except Exception as exc:
        g = grader.Grade("error", detail="grading failed: %s" % exc)
    if not answer:
        g.detail = "; ".join(x for x in ("no final answer", g.detail) if x)
    run.verdict, run.cost, run.optimum = g.verdict, g.cost, g.optimum
    run.detail = "; ".join(x for x in (run.detail, g.detail) if x)
    name = "%s-%s-%s-%d.md" % (run.scenario, run.arm, run.model.replace("/", "_"), run.rep)
    path = outdir / "transcripts" / name
    path.write_text(to_markdown(run, messages, g), encoding="utf-8")
    run.transcript = str(path.relative_to(outdir))
    return run


# -- reporting ----------------------------------------------------------------

def table(runs: List[Run]) -> str:
    models = sorted({r.model for r in runs})
    keys = sorted({(r.scenario, r.arm) for r in runs},
                  key=lambda k: (k[0], ARMS.index(k[1])))
    out = ["| scenario | arm | " + " | ".join("`%s`" % m for m in models) + " |",
           "|---|---|" + "---|" * len(models)]
    for sc, arm in keys:
        cells = []
        for m in models:
            rs = [r for r in runs if (r.scenario, r.arm, r.model) == (sc, arm, m)]
            if not rs:
                cells.append("")
                continue
            ok = sum(r.verdict == grader.OPTIMAL for r in rs)
            others = sorted({r.verdict for r in rs if r.verdict != grader.OPTIMAL})
            cells.append("%d/%d%s" % (ok, len(rs), (" (" + ", ".join(others) + ")")
                                      if others else ""))
        out.append("| %s | %s | %s |" % (sc, arm, " | ".join(cells)))
    return "\n".join(out)


def details(runs: List[Run]) -> str:
    out = ["| run | verdict | cost/opt | turns | tools | tokens | s | transcript |",
           "|---|---|---|---|---|---|---|---|"]
    for r in runs:
        out.append("| %s %s %s #%d | %s | %s/%s | %d | %s | %d | %.0f | [md](%s) |" % (
            r.scenario, r.arm, r.model, r.rep, r.verdict,
            "-" if r.cost is None else "%g" % r.cost,
            "-" if r.optimum is None else "%g" % r.optimum, r.turns,
            ", ".join("%s×%d" % kv for kv in r.tool_calls.items()) or "-",
            r.tokens, r.seconds, r.transcript))
    return "\n".join(out)


# -- commands -----------------------------------------------------------------

async def cmd_run(a) -> int:
    dry = a.dry_run
    if not dry and "OPENROUTER_API_KEY" not in os.environ:
        print("OPENROUTER_API_KEY not set (use --dry-run to test the pipeline)",
              file=sys.stderr)
        return 2
    scs = [scenarios.load(n) for n in a.scenarios]
    arms = a.arm.split(",")
    bad = [x for x in arms if x not in ARMS]
    if bad:
        print("unknown arm(s) %s; choose from %s" % (bad, ", ".join(ARMS)), file=sys.stderr)
        return 2
    models = ["dry-run"] if dry else a.model.split(",")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = pathlib.Path(a.out or HERE / "results" / stamp)
    (outdir / "transcripts").mkdir(parents=True, exist_ok=True)
    jobs = [Run(sc.name, arm, m, rep) for sc, arm, m, rep in itertools.product(
        scs, arms, models, range(1, a.repeats + 1))]
    by_name = {sc.name: sc for sc in scs}

    import httpx
    async with contextlib.AsyncExitStack() as stack:
        session, mcp_tools = None, []
        if "pddlpy" in arms:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            cmd, *cmd_args = a.server_cmd.split()
            read, write = await stack.enter_async_context(
                stdio_client(StdioServerParameters(command=cmd, args=cmd_args)))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
        http = await stack.enter_async_context(httpx.AsyncClient())
        client = None if dry else OpenRouter(http)
        sem = asyncio.Semaphore(a.jobs)
        log = (outdir / "results.jsonl").open("a", encoding="utf-8")
        stack.callback(log.close)

        async def go(r: Run) -> Run:
            async with sem:
                await one_run(r, by_name[r.scenario], client, client, a.grader_model,
                              session, mcp_tools, a.max_turns, dry, outdir)
            log.write(json.dumps(asdict(r)) + "\n")
            log.flush()
            print("%-12s %-7s %-34s #%d  %-16s %s" % (
                r.scenario, r.arm, r.model, r.rep, r.verdict,
                "" if r.cost is None else "cost %g/%g" % (r.cost, r.optimum)), flush=True)
            return r

        runs = await asyncio.gather(*(go(j) for j in jobs))

    report = "# Playground results %s\n\n%s\n\n## Runs\n\n%s\n" % (
        stamp, table(runs), details(runs))
    (outdir / "results.md").write_text(report, encoding="utf-8")
    print("\n" + table(runs) + "\n\nresults: %s" % (outdir / "results.md"))
    return 0


def cmd_list(a) -> int:
    for sc in scenarios.all_scenarios():
        print("%-22s optimum %-6g %s" % (sc.name, sc.optimal_cost, sc.source))
    return 0


def cmd_show(a) -> int:
    print(scenarios.load(a.scenario).text)
    return 0


def cmd_check(a) -> int:
    scs = [scenarios.load(n) for n in a.scenarios] or scenarios.all_scenarios()
    rc = 0
    for sc in scs:
        c = scenarios.check(sc, a.timeout)
        ok = c.cost is not None and abs(c.cost - sc.optimal_cost) < 1e-9
        rc |= not ok
        print("%-22s %s  %s cost %s (meta %g), %d steps, %.1fs %s" % (
            sc.name, "ok " if ok else "BAD", sc.planner, c.cost, sc.optimal_cost,
            len(c.plan), c.seconds, c.message))
        if a.plan:
            print("    " + "\n    ".join(c.plan))
    return rc


def cmd_grade(a) -> int:
    sc = scenarios.load(a.scenario)
    answer = pathlib.Path(a.answer).read_text(encoding="utf-8")
    extractor = None
    if a.grader_model and "OPENROUTER_API_KEY" in os.environ:
        import httpx

        def extractor(prompt: str) -> str:
            r = httpx.post(OPENROUTER_URL, timeout=600, json={
                "model": a.grader_model, "temperature": 0,
                "messages": [{"role": "user", "content": prompt}]},
                headers={"Authorization": "Bearer %s" % os.environ["OPENROUTER_API_KEY"]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"].get("content") or ""
    g = grader.grade(sc, answer, extractor)
    print(json.dumps(asdict(g), indent=1))
    return 0 if g.passed else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="scenarios and their optimum")
    p = sub.add_parser("show", help="print a scenario's English text")
    p.add_argument("scenario")
    p = sub.add_parser("check", help="solve the reference problems")
    p.add_argument("scenarios", nargs="*")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--plan", action="store_true", help="print the reference plans")
    p = sub.add_parser("grade", help="grade an answer file against a scenario")
    p.add_argument("scenario")
    p.add_argument("answer")
    p.add_argument("--grader-model", default=DEFAULT_GRADER)
    p = sub.add_parser("run", help="run scenarios x arms x models")
    p.add_argument("scenarios", nargs="+")
    p.add_argument("--arm", default="bare", help="comma list of %s" % ",".join(ARMS))
    p.add_argument("--model", default="openai/gpt-5", help="comma list of OpenRouter ids")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--jobs", type=int, default=4, help="concurrent runs")
    p.add_argument("--max-turns", type=int, default=30)
    p.add_argument("--grader-model", default=DEFAULT_GRADER,
                   help="extractor model (temperature 0)")
    p.add_argument("--server-cmd", default="uv run --project %s --extra mcp pddlpy-mcp" % REPO,
                   help="MCP server (default: this checkout); published: "
                        "'uvx --from pddlpy[mcp] pddlpy-mcp'")
    p.add_argument("--out", help="results dir (default results/<stamp>)")
    p.add_argument("--dry-run", action="store_true", help="canned replies, no API key")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return asyncio.run(cmd_run(a))
    return {"list": cmd_list, "show": cmd_show, "check": cmd_check,
            "grade": cmd_grade}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
