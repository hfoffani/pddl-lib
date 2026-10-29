"""MCP server (#86): parse / ground / solve / validate / validate_plan /
simulate as Model Context Protocol tools.

The runtime counterpart of the static Agent Skill in ``skills/pddlpy/`` —
an LLM/agent connects over stdio and drives the library through tools
that mirror the CLI subcommands (#85) and return the same JSON
shapes from ``pddlpy.serialize``.

Requires the optional ``mcp`` dependency: ``pip install pddlpy[mcp]``.
Run with the ``pddlpy-mcp`` console script (stdio transport).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.mcpserver import MCPServer

from pddlpy.diagnostics import diagnose
from pddlpy.pddl import DomainProblem
from pddlpy.planning import load_plan, registry, simulate, validate_plan
from pddlpy.planning import solve as solve_plan
from pddlpy.serialize import (
    domain_problem_dict,
    operator_dict,
    simulation_dict,
    solve_dict,
    validation_dict,
)

server = MCPServer(
    "pddlpy",
    instructions=(
        "Parse, validate, ground and solve PDDL domain/problem pairs, and "
        "validate or simulate plans. All tools take filesystem paths to a "
        "domain file and a problem file."
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
    grounded instance with its parameters, preconditions and effects. Fails
    with the list of known operators if ``operator`` is not in the domain.
    Untyped domains can ground to many instances (objects^parameters)."""
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
def solve(domain_file: str, problem_file: str, planner: str = "astar",
          max_expansions: Optional[int] = None,
          timeout: Optional[float] = None) -> Dict[str, Any]:
    """Search for a plan on a PDDL domain/problem pair. ``planner`` is one of
    the registered planners: bfs, astar (default), gbfs, ucs (cost-optimal for
    :action-costs), or temporal (required for :durative-actions; steps carry
    start/duration/end and the result a ``makespan``). ``max_expansions`` /
    ``timeout`` (seconds) bound the search. Returns the plan
    (solved/cost/length/steps) and ``status``: solved, unsolvable (search
    space exhausted: no plan exists) or limit (stopped at a bound: try a
    larger one or another planner). ``validated`` says whether the plan was
    checked with validate_plan. Fails if the domain declares :requirements
    the chosen planner does not support."""
    if planner not in registry.names():
        raise ValueError(
            "unknown planner %r; known: %s" % (planner, registry.names())
        )
    dp = DomainProblem(domain_file, problem_file)
    outcome = solve_plan(dp, planner, max_expansions, timeout)
    return {"planner": planner, **solve_dict(outcome)}


@server.tool()
def validate(domain_file: str, problem_file: str) -> Dict[str, Any]:
    """Check a PDDL domain/problem pair for common translation errors:
    syntax errors, atoms over undeclared predicates, ground atoms naming
    unknown objects, operators grounding to zero instances, and malformed
    durative actions. Returns {valid, issues:[{severity, check, message}]}.
    Run this after writing or editing PDDL, before ground/solve."""
    return diagnose(domain_file, problem_file)


@server.tool(name="validate_plan")
def validate_plan_tool(domain_file: str, problem_file: str, plan: str) -> Dict[str, Any]:
    """Check that a plan executes from the initial state and reaches the
    goal, with VAL's semantics. ``plan`` is the plan text: one
    '(action arg ...)' per line, 'time: (action arg ...) [duration]' for
    temporal plans, or the JSON ``solve`` returns. Returns {valid, failure};
    failure has kind (precondition, goal, unknown-action, arity, type,
    duration, invariant, mutex, ...), message, the 1-based step, its action,
    the unmet conditions or goal atoms, and the state at that point. Fails
    when the plan cannot be read, or when pddlpy cannot judge the domain
    (syntax errors, goals other than a conjunction of atoms, durative
    actions with numeric or conditional parts)."""
    return validation_dict(
        validate_plan(DomainProblem(domain_file, problem_file), load_plan(plan)))


@server.tool(name="simulate")
def simulate_tool(domain_file: str, problem_file: str, plan: str) -> Dict[str, Any]:
    """Execute a plan (same ``plan`` text as validate_plan) and return the
    state after each step, or after each start and end of a durative step:
    {executed, failure, trace:[{time, event, step, action, state}],
    final_state}. Stops at the first step that cannot run; the goal is not
    checked."""
    return simulation_dict(
        simulate(DomainProblem(domain_file, problem_file), load_plan(plan)))


def main() -> None:
    """Run the server on stdio."""
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
