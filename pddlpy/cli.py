"""Command-line interface (#85): drive pddlpy without writing Python.

Three subcommands over a domain/problem pair, all emitting JSON on stdout:

    pddlpy parse    DOMAIN PROBLEM             # object-model summary
    pddlpy ground   DOMAIN PROBLEM OPERATOR    # grounded instances of one action
    pddlpy solve    DOMAIN PROBLEM [--planner NAME]
    pddlpy validate DOMAIN PROBLEM             # diagnostics (#94)

Exit codes: 0 success; 1 solve found no plan / validate found issues;
2 bad input (missing file, unknown operator/planner, unsupported
:requirements).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from pddlpy.diagnostics import diagnose
from pddlpy.pddl import DomainProblem
from pddlpy.planning import PlannerError, get, registry
from pddlpy.serialize import domain_problem_dict, operator_dict, plan_dict


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
    ):
        cmd = sub.add_parser(name, help=help_)
        cmd.add_argument("domain", help="path to the domain PDDL file")
        cmd.add_argument("problem", help="path to the problem PDDL file")
        if name == "ground":
            cmd.add_argument("operator", help="operator name to ground")
        if name == "solve":
            cmd.add_argument(
                "--planner",
                default="astar",
                choices=registry.names(),
                help="planner to use (default: astar)",
            )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "validate":
        try:
            result = diagnose(args.domain, args.problem)
        except FileNotFoundError as exc:
            print("pddlpy: error: %s" % exc, file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2))
        return 0 if not result["issues"] else 1

    try:
        dp = DomainProblem(args.domain, args.problem)
    except FileNotFoundError as exc:
        print("pddlpy: error: %s" % exc, file=sys.stderr)
        return 2

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
            plan = get(args.planner).solve(dp)
        except PlannerError as exc:
            print("pddlpy: error: %s" % exc, file=sys.stderr)
            return 2
        result = {"planner": args.planner, **plan_dict(plan)}
        print(json.dumps(result, indent=2))
        return 0 if plan is not None else 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
