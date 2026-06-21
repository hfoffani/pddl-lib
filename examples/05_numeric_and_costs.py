"""Example 05 — Numeric fluents (#11) and action costs (#3).

Numeric fluents: the transport domain guards ``drive`` with ``(>= (fuel ?v) ...)``
and decreases fuel as an effect; the planner respects the numeric constraints.

Action costs: the travel domain accrues ``total-cost``; ``ucs`` is cost-optimal
and prefers a cheaper multi-hop route over a single expensive hop, whereas
``bfs`` (which minimizes the *number* of actions) does not.
"""
import os

from pddlpy import DomainProblem
from pddlpy.planning import get

PDDL = os.path.join(os.path.dirname(__file__), "pddl")


def _dp(name):
    return DomainProblem(
        os.path.join(PDDL, "%s-domain.pddl" % name),
        os.path.join(PDDL, "%s-problem.pddl" % name),
    )


def main():
    nt = _dp("numeric-transport")
    print("functions:", nt.functions())
    print("initial numeric valuation:", nt.initial_numeric())
    plan = get("bfs").solve(nt)
    print("numeric-transport plan (fuel-aware):", plan.action_names())

    travel = _dp("travel")
    print("\nmetric:", travel.metric())
    bfs_plan = get("bfs").solve(travel)
    ucs_plan = get("ucs").solve(travel)
    print("bfs : %d actions, cost %s" % (len(bfs_plan), bfs_plan.cost))
    print("ucs : %d actions, cost %s  <- cost-optimal" % (len(ucs_plan), ucs_plan.cost))


if __name__ == "__main__":
    main()
