"""Command-line interface (#85): drive pddlpy without writing Python.

Subcommands over a domain/problem pair, all emitting JSON on stdout:

    pddlpy parse         DOMAIN PROBLEM             # object-model summary
    pddlpy ground        DOMAIN PROBLEM OPERATOR    # grounded instances of one action
    pddlpy solve         DOMAIN PROBLEM [--planner NAME] [--max-expansions N] [--timeout S]
    pddlpy validate      DOMAIN PROBLEM             # diagnostics (#94)
    pddlpy validate-plan DOMAIN PROBLEM PLAN        # plan verdict (#166)
    pddlpy simulate      DOMAIN PROBLEM PLAN        # state after each step (#166)

PLAN is a plan file in the IPC format or JSON (``solve`` output works), or
``-`` for stdin.

``solve`` reports ``status``: ``solved``, ``unsolvable`` (search space
exhausted) or ``limit`` (stopped at --max-expansions / --timeout), and
validates the plan it found (``validated``).

Exit codes: 0 success; 1 solve proved there is no plan / validate found
issues / the plan is invalid (validate-plan) or does not execute
(simulate); 2 bad input (missing file, unreadable plan, unknown
operator/planner, unsupported :requirements, a plan pddlpy cannot judge);
3 solve hit a limit before finding a plan.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from pddlpy.diagnostics import diagnose
from pddlpy.pddl import DomainProblem
from pddlpy.planning import (
    LIMIT,
    SOLVED,
    PlannerError,
    load_plan,
    registry,
    simulate,
    solve,
    validate_plan,
)
from pddlpy.serialize import (
    domain_problem_dict,
    operator_dict,
    simulation_dict,
    solve_dict,
    validation_dict,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pddlpy",
        description="Parse, ground and solve PDDL domain/problem pairs (JSON output).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_ in (
        ("parse", "summarize the parsed domain/problem pair"),
        ("ground", "list the grounded instances of one operator"),
        ("solve", "search for a plan"),
        ("validate", "check the pair for common translation errors"),
        ("validate-plan", "check that a plan reaches the goal"),
        ("simulate", "list the state after each step of a plan"),
    ):
        cmd = sub.add_parser(name, help=help_)
        cmd.add_argument("domain", help="path to the domain PDDL file")
        cmd.add_argument("problem", help="path to the problem PDDL file")
        if name in ("validate-plan", "simulate"):
            cmd.add_argument("plan", help="plan file (IPC format or JSON), or - for stdin")
        if name == "ground":
            cmd.add_argument("operator", help="operator name to ground")
        if name == "solve":
            cmd.add_argument(
                "--planner",
                default="astar",
                choices=registry.names(),
                help="planner to use (default: astar)",
            )
            cmd.add_argument("--max-expansions", type=int, metavar="N",
                             help="stop after expanding N states (exit 3)")
            cmd.add_argument("--timeout", type=float, metavar="SECONDS",
                             help="stop after SECONDS of search (exit 3)")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "validate":
        try:
            result = diagnose(args.domain, args.problem)
        except FileNotFoundError as exc:
            print("pddlpy: error: %s" % exc, file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if not result["issues"] else 1

    try:
        dp = DomainProblem(args.domain, args.problem)
    except FileNotFoundError as exc:
        print("pddlpy: error: %s" % exc, file=sys.stderr)
        return 2

    if args.command in ("validate-plan", "simulate"):
        return _check_plan(args, dp)

    if args.command == "parse":
        result = domain_problem_dict(dp)
    elif args.command == "ground":
        if args.operator not in dp.operators():
            print(
                "pddlpy: error: unknown operator %r; known: %s"
                % (args.operator, sorted(dp.operators())),
                file=sys.stderr,
            )
            return 2
        result = {
            "operator": args.operator,
            "groundings": [operator_dict(op) for op in dp.ground_operator(args.operator)],
        }
    else:  # solve
        try:
            outcome = solve(dp, args.planner, args.max_expansions, args.timeout)
        except PlannerError as exc:
            print("pddlpy: error: %s" % exc, file=sys.stderr)
            return 2
        result = {"planner": args.planner, **solve_dict(outcome)}
        print(json.dumps(result, indent=2, allow_nan=False))
        return {SOLVED: 0, LIMIT: 3}.get(outcome.status, 1)

    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


def _check_plan(args: argparse.Namespace, dp: DomainProblem) -> int:
    try:
        if args.plan == "-":
            text = sys.stdin.read()
        else:
            with open(args.plan, encoding="utf-8") as f:
                text = f.read()
        steps = load_plan(text)
        if args.command == "simulate":
            sim = simulate(dp, steps)
            print(json.dumps(simulation_dict(sim), indent=2, allow_nan=False))
            return 0 if sim.executed else 1
        result = validate_plan(dp, steps)
    except (OSError, UnicodeError, PlannerError) as exc:  # unreadable or unjudgeable
        print("pddlpy: error: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(validation_dict(result), indent=2, allow_nan=False))
    return 0 if result.valid else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
