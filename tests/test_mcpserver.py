"""The MCP server (#86): parse / ground / solve tools over the object model."""
import asyncio
import json
import os
import subprocess
import sys

import pytest
from mcp import Client, StdioServerParameters

from pddlpy import mcpserver
from pddlpy.mcpserver import (
    ground,
    parse,
    server,
    simulate_tool,
    solve,
    validate,
    validate_plan_tool,
)

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _files(name):
    return (
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


# --- tool functions (direct) ----------------------------------------------

def test_parse_summary():
    out = parse(*_files("blocksworld"))
    assert "pick-up" in out["operators"]
    assert ["on", "a", "b"] in out["goals"]
    assert out["metric"] is None


def test_ground_operator():
    out = ground(*_files("blocksworld"), operator="pick-up")
    assert out["operator"] == "pick-up"
    g = next(g for g in out["groundings"] if g["parameters"] == {"?x": "a"})
    assert ["holding", "a"] in g["effect_pos"]


def test_ground_unknown_operator():
    with pytest.raises(ValueError, match="unknown operator 'fly'"):
        ground(*_files("blocksworld"), operator="fly")


def test_solve_default_planner():
    out = solve(*_files("blocksworld"))
    assert out["planner"] == "astar" and out["solved"] is True
    assert out["length"] == len(out["steps"]) > 0


def test_solve_temporal_schedule():
    # #119: the solve tool surfaces TemporalPlan schedules.
    out = solve(*_files("temporal-weld"), planner="temporal")
    assert out["solved"] is True and out["makespan"] == out["cost"]
    step = out["steps"][0]
    assert step["end"] == step["start"] + step["duration"]


def test_solve_no_plan(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain toy) (:predicates (p) (q))"
        " (:action a :parameters () :precondition (q) :effect (p)))"
    )
    problem.write_text("(define (problem t1) (:domain toy) (:init) (:goal (p)))")
    out = solve(str(domain), str(problem), planner="bfs")
    assert out["solved"] is False and out["steps"] is None
    assert out["status"] == "unsolvable"


def test_solve_limit():
    out = solve(*_files("gripper"), planner="bfs", max_expansions=2)
    assert out["status"] == "limit" and out["solved"] is False
    out = solve(*_files("gripper"), timeout=60)
    assert (out["status"], out["validated"]) == ("solved", True)


def test_solve_unknown_planner():
    with pytest.raises(ValueError, match="unknown planner 'nosuch'"):
        solve(*_files("blocksworld"), planner="nosuch")


# --- through the MCP layer -------------------------------------------------

def test_validate_clean_pair():
    assert validate(*_files("blocksworld")) == {"valid": True, "issues": []}


def test_validate_plan_from_solve():
    files = _files("gripper")
    plan = json.dumps(solve(*files))
    assert validate_plan_tool(*files, plan=plan) == {"valid": True, "failure": None}
    out = validate_plan_tool(*files, plan="(move rooma roomb)\n(move rooma roomb)\n")
    assert out["failure"]["kind"] == "precondition" and out["failure"]["step"] == 2


def test_simulate_tool():
    out = simulate_tool(*_files("durative-action"), plan="0: (go a b) [5]")
    assert out["executed"] and [p["event"] for p in out["trace"]] == ["start", "end"]


def test_simulate_tool_non_finite_fluent(tmp_path):
    """IEEE division by zero yields an infinity: a string, not null."""
    domain = tmp_path / "d.pddl"
    domain.write_text("(define (domain d) (:requirements :fluents) (:predicates (p))"
                      " (:functions (f)) (:action a :parameters () :precondition (and)"
                      " :effect (and (p) (assign (f) (/ 1 0)))))")
    problem = tmp_path / "p.pddl"
    problem.write_text("(define (problem p) (:domain d) (:init (= (f) 0)) (:goal (p)))")
    result = asyncio.run(server.call_tool(
        "simulate", {"domain_file": str(domain), "problem_file": str(problem), "plan": "(a)"}))
    assert result.structured_content["result"]["final_state"]["fluents"] == {"f": "inf"}


def test_tools_registered():
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == [
        "ground", "parse", "simulate", "solve", "validate", "validate_plan"]
    for t in tools:
        assert t.description  # every tool documents itself


def test_call_tool_returns_structured_content():
    domain, problem = _files("travel")
    result = asyncio.run(
        server.call_tool(
            "solve",
            {"domain_file": domain, "problem_file": problem, "planner": "ucs"},
        )
    )
    out = result.structured_content["result"]  # MCPServer wraps plain-dict returns
    assert out["solved"] is True and out["cost"] == 2.0


# --- protocol versions over stdio (#150) -----------------------------------

def _stdio_server():
    return subprocess.Popen(
        [sys.executable, "-m", "pddlpy.mcpserver"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True,
    )


def _rpc(proc, message):
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    if "id" in message:
        return json.loads(proc.stdout.readline())


@pytest.mark.parametrize(
    "version", ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]
)
def test_stdio_handshake_versions(version):
    # Pre-2026 clients open with `initialize`; the server echoes their version.
    proc = _stdio_server()
    try:
        init = _rpc(proc, {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": version, "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        })
        assert init["result"]["protocolVersion"] == version
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert len(tools["result"]["tools"]) == 6
    finally:
        proc.kill()
        proc.wait()


@pytest.mark.parametrize(
    "mode, version", [("auto", "2026-07-28"), ("legacy", "2025-11-25")]
)
def test_stdio_sdk_client(mode, version):
    # A current SDK client negotiates 2026-07-28 (no handshake); "legacy"
    # forces the initialize handshake.
    domain, problem = _files("blocksworld")
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "pddlpy.mcpserver"]
    )

    async def run():
        async with Client(params, mode=mode) as client:
            result = await client.call_tool(
                "validate", {"domain_file": domain, "problem_file": problem}
            )
            return client.protocol_version, result.structured_content["result"]

    negotiated, out = asyncio.run(run())
    assert negotiated == version
    assert out == {"valid": True, "issues": []}


# --- entry point -----------------------------------------------------------

def test_main_runs_stdio(monkeypatch):
    calls = []
    monkeypatch.setattr(mcpserver.server, "run", lambda *a, **kw: calls.append((a, kw)))
    mcpserver.main()
    assert calls == [((), {})]
