"""Example 04 — Reference planners (#1).

The optional ``pddlpy.planning`` layer ships blind-search reference planners
behind a registry. Look one up by name and call ``solve(dp)``; you get a
``Plan`` (ordered grounded actions + a cost) or ``None``.
"""
import os

from pddlpy import DomainProblem
from pddlpy.planning import get, registry

PDDL = os.path.join(os.path.dirname(__file__), "pddl")


def _dp(name):
    return DomainProblem(
        os.path.join(PDDL, "%s-domain.pddl" % name),
        os.path.join(PDDL, "%s-problem.pddl" % name),
    )


def main():
    print("registered planners:", registry.names())

    bw = _dp("blocksworld")
    plan = get("astar").solve(bw)
    print("\nblocksworld via A* — %d actions, cost %s:" % (len(plan), plan.cost))
    for op_name, binding in plan.action_names():
        print("  %s %s" % (op_name, binding))

    grip = _dp("gripper")
    plan = get("bfs").solve(grip)
    print("\ngripper via BFS — %d actions:" % len(plan))
    for op_name, binding in plan.action_names():
        print("  %s %s" % (op_name, binding))


if __name__ == "__main__":
    main()
