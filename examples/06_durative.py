"""Example 06 — Durative actions (#23).

Durative actions are parsed and grounded into a ``DurativeAction`` (time-tagged
``at start`` / ``over all`` / ``at end`` conditions and effects, plus a
duration). ``DurativeState`` answers whether a grounded action can *start* in a
state, and ``validate_durative_actions`` checks they are well-formed.

This example stops at the model. To *solve* durative domains use the
``temporal`` planner (#84): ``get("temporal").solve(dp)`` returns a
``TemporalPlan`` with per-step start times and a ``makespan``, under sequential
semantics (no required concurrency). The STRIPS planners (bfs/astar/gbfs/ucs)
refuse ``:durative-actions``.
"""
import os

from pddlpy import DomainProblem
from pddlpy.planning import DurativeState, validate_durative_actions

PDDL = os.path.join(os.path.dirname(__file__), "pddl")


def main():
    dp = DomainProblem(
        os.path.join(PDDL, "durative-action-domain.pddl"),
        os.path.join(PDDL, "durative-action-problem.pddl"),
    )

    validate_durative_actions(dp)  # raises DurativeValidationError if malformed
    print("durative actions:", list(dp.durative_operators()))

    state = DurativeState.from_problem(dp)
    print("initial state:", sorted(state))
    print("\ngrounded 'go' instances — can each START now?")
    for ga in dp.ground_durative_operator("go"):
        print(
            "  %s  duration=%s  at-start-applicable=%s"
            % (ga.variable_list, ga.duration, state.applicable(ga))
        )


if __name__ == "__main__":
    main()
