"""The MCP server (#86): parse / ground / solve tools over the object model."""
import asyncio
import os

import pytest

from pddlpy import mcpserver
from pddlpy.mcpserver import ground, parse, server, solve

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


def test_solve_unknown_planner():
    with pytest.raises(ValueError, match="unknown planner 'nosuch'"):
        solve(*_files("blocksworld"), planner="nosuch")


# --- through the MCP layer -------------------------------------------------

def test_tools_registered():
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == ["ground", "parse", "solve"]
    for t in tools:
        assert t.description  # every tool documents itself


def test_call_tool_returns_structured_content():
    domain, problem = _files("travel")
    _, structured = asyncio.run(
        server.call_tool(
            "solve",
            {"domain_file": domain, "problem_file": problem, "planner": "ucs"},
        )
    )
    out = structured["result"]  # FastMCP wraps plain-dict returns
    assert out["solved"] is True and out["cost"] == 2.0


# --- entry point -----------------------------------------------------------

def test_main_runs_stdio(monkeypatch):
    calls = []
    monkeypatch.setattr(mcpserver.server, "run", lambda *a, **kw: calls.append((a, kw)))
    mcpserver.main()
    assert calls == [((), {})]
