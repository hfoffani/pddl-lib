"""MCP server (#86): parse / ground / solve as Model Context Protocol tools.

The runtime counterpart of the static Agent Skill in ``skills/pddlpy/`` —
an LLM/agent connects over stdio and drives the library through three
tools that mirror the CLI subcommands (#85) and return the same JSON
shapes from ``pddlpy.serialize``.

Requires the optional ``mcp`` dependency: ``pip install pddlpy[mcp]``.
Run with the ``pddlpy-mcp`` console script (stdio transport).
"""
from __future__ import annotations

from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from pddlpy.diagnostics import diagnose
from pddlpy.pddl import DomainProblem
from pddlpy.planning import get, registry
from pddlpy.serialize import domain_problem_dict, operator_dict, plan_dict

server = FastMCP(
    "pddlpy",
    instructions=(
        "Parse, ground and solve PDDL domain/problem pairs. All tools take "
        "filesystem paths to a domain file and a problem file."
    ),
)


@server.tool()
def parse(domain_file: str, problem_file: str) -> Dict[str, Any]:
    """Parse a PDDL domain/problem pair and return an object-model summary:
    requirements, objects, types, predicates, operators, initial state,
    goals, numeric fluents and metric."""
    dp = DomainProblem(domain_file, problem_file)
    return domain_problem_dict(dp)


@server.tool()
def ground(domain_file: str, problem_file: str, operator: str) -> Dict[str, Any]:
    """Ground one operator of a PDDL domain/problem pair and return every
    grounded instance with its parameters, preconditions and effects."""
    dp = DomainProblem(domain_file, problem_file)
    if operator not in dp.operators():
        raise ValueError(
            "unknown operator %r; known: %s" % (operator, sorted(dp.operators()))
        )
    return {
        "operator": operator,
        "groundings": [operator_dict(op) for op in dp.ground_operator(operator)],
    }


@server.tool()
def solve(domain_file: str, problem_file: str, planner: str = "astar") -> Dict[str, Any]:
    """Search for a plan on a PDDL domain/problem pair. ``planner`` is one of
    the registered planners (bfs, astar, gbfs, ucs; default astar). Returns
    the plan (solved/cost/length/steps), with ``solved: false`` when the
    search exhausts without reaching the goal."""
    if planner not in registry.names():
        raise ValueError(
            "unknown planner %r; known: %s" % (planner, registry.names())
        )
    dp = DomainProblem(domain_file, problem_file)
    plan = get(planner).solve(dp)
    return {"planner": planner, **plan_dict(plan)}


@server.tool()
def validate(domain_file: str, problem_file: str) -> Dict[str, Any]:
    """Check a PDDL domain/problem pair for common translation errors:
    syntax errors, atoms over undeclared predicates, ground atoms naming
    unknown objects, operators grounding to zero instances, and malformed
    durative actions. Returns {valid, issues:[{severity, check, message}]}.
    Run this after writing or editing PDDL, before ground/solve."""
    return diagnose(domain_file, problem_file)


def main() -> None:
    """Run the server on stdio."""
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
