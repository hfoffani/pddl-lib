"""Run one playground conversation through the Codex CLI (``codex exec``),
signed in with a ChatGPT account: subscription models, no API key.

Model ids ``codex:<slug>`` (e.g. ``codex:gpt-6.1-sol``; ``codex debug models``
lists the slugs) select this driver. The arms differ from the OpenRouter
ones, because Codex brings its own agent prompt and tools:

    bare     shell, code mode, web search, apps and plugins off: no tool
             can compute (``exec`` fails closed)
    python   Codex's shell in its ``workspace-write`` sandbox (writes only in
             the run's temp dir, no network); it can read the rest of the disk
    pddlpy   the pddlpy MCP server and Codex's file edits; shell and code mode
             off

Each run gets a fresh ``CODEX_HOME`` holding only a link to the account's
``auth.json``, so neither ``~/.codex/config.toml`` nor the global
``AGENTS.md`` reaches the model. The JSONL events become chat messages in
the playground's format, so grading, tables and transcripts are shared.
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shlex
import tempfile
from typing import List, Tuple

PREFIX = "codex:"

# Like playground.SYSTEM, but Codex writes files with its own tools.
SYSTEM = {
    "bare": None,
    "python": "You can run Python programs with the shell.",
    "pddlpy": "You have a PDDL planner. Save PDDL domain and problem files in the "
              "working directory, and use the pddlpy tools (validate, solve, ...) "
              "on them.",
}

_OFF = ["apps", "plugins", "browser_use", "computer_use", "in_app_browser",
        "multi_agent", "collaboration_modes", "skill_search"]


def command(arm: str, slug: str, workdir: pathlib.Path, server_cmd: str) -> List[str]:
    off = list(_OFF)
    if arm == "bare":  # every tool runs through code mode
        off += ["code_mode_host"]
    if arm != "python":
        off += ["shell_tool", "unified_exec"]
    argv = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--json",
            "-C", str(workdir), "-m", slug,
            "-s", "read-only" if arm == "bare" else "workspace-write",
            "-c", 'web_search="disabled"', "-c", "skills.include_instructions=false"]
    for f in off:
        argv += ["--disable", f]
    if arm == "pddlpy":
        cmd, *args = shlex.split(server_cmd)
        argv += ["-c", "mcp_servers.pddlpy.command=%s" % json.dumps(cmd),
                 "-c", "mcp_servers.pddlpy.args=%s" % json.dumps(args),
                 # exec cannot ask: without this every MCP call fails
                 "-c", 'mcp_servers.pddlpy.default_tools_approval_mode="approve"']
    return argv + ["-"]


def codex_home(workdir: pathlib.Path) -> pathlib.Path:
    home = workdir.parent / (workdir.name + "-codex-home")
    home.mkdir()
    auth = pathlib.Path(os.environ.get("CODEX_HOME", pathlib.Path.home() / ".codex"))
    (home / "auth.json").symlink_to(auth / "auth.json")
    return home


def to_messages(events: List[dict]) -> Tuple[List[dict], int, List[str]]:
    """Codex JSONL events -> (playground chat messages, tokens, errors)."""
    messages: List[dict] = []
    tokens, errors = 0, []
    for e in events:
        t = e.get("type")
        if t == "turn.completed":
            u = e.get("usage") or {}
            tokens += u.get("input_tokens", 0) + u.get("output_tokens", 0)
        elif t in ("error", "turn.failed"):
            errors.append(e.get("message") or (e.get("error") or {}).get("message", ""))
        if t != "item.completed":
            continue
        it = e["item"]
        kind, n = it.get("type"), len(messages)
        if kind == "agent_message":
            messages.append({"role": "assistant", "content": it.get("text", "")})
        elif kind == "reasoning":
            messages.append({"role": "assistant", "reasoning": it.get("text", "")})
        elif kind in ("command_execution", "mcp_tool_call", "file_change"):
            if kind == "command_execution":
                name, args = "shell", {"command": it.get("command")}
                out = {"exit_code": it.get("exit_code"),
                       "output": it.get("aggregated_output", "")}
            elif kind == "mcp_tool_call":
                name, args = it.get("tool", "?"), it.get("arguments") or {}
                res = it.get("result") or {}
                out = ((res.get("structured_content") or {}).get("result", res)
                       if res else it.get("error"))
            else:
                name, args, out = "file_change", {"changes": it.get("changes")}, ""
            cid = "codex_%d" % n
            messages.append({"role": "assistant", "content": None, "tool_calls": [
                {"id": cid, "type": "function",
                 "function": {"name": name, "arguments": json.dumps(args)}}]})
            messages.append({"role": "tool", "tool_call_id": cid,
                             "content": out if isinstance(out, str) else json.dumps(out)})
        elif kind == "error":
            errors.append(it.get("message", ""))
    return messages, tokens, [x for x in errors if x]


async def converse(run, sc, server_cmd: str, timeout: float) -> List[dict]:
    """One run; fills run.turns/tool_calls/tokens/detail like playground.converse."""
    workdir = pathlib.Path(tempfile.mkdtemp(prefix="pddlpy-play-"))
    prompt = sc.text if not SYSTEM[run.arm] else "%s\n\n%s" % (SYSTEM[run.arm], sc.text)
    proc = await asyncio.create_subprocess_exec(
        *command(run.arm, run.model[len(PREFIX):], workdir, server_cmd),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "CODEX_HOME": str(codex_home(workdir))})
    try:
        out, _ = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        out, _ = await proc.communicate()
        run.detail = "codex timed out after %ds" % timeout
    events = [json.loads(line) for line in out.decode().splitlines()
              if line.startswith("{")]
    body, run.tokens, errors = to_messages(events)
    # notices, not failures: the bare arm turns code mode off on purpose
    errors = [x for x in errors if not x.startswith("Code Mode is unavailable")]
    if errors:
        run.detail = "; ".join(x for x in [run.detail] + errors if x)
    run.turns = sum(m["role"] == "assistant" for m in body)
    for m in body:
        for tc in m.get("tool_calls") or []:
            name = tc["function"]["name"]
            run.tool_calls[name] = run.tool_calls.get(name, 0) + 1
    return [{"role": "user", "content": prompt}] + body
