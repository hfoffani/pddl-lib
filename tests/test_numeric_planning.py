"""#11 numeric fluents — planning layer: numeric State, applicability,
successor generation, and solving."""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.planning import State, GroundedTask, BFSPlanner, AStarPlanner, GBFSPlanner, get

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _transport(problemfile="numeric-transport-problem.pddl"):
    return DomainProblem(
        os.path.join(CORPUS, "numeric-transport-domain.pddl"),
        os.path.join(CORPUS, problemfile),
    )


def test_state_carries_fluents():
    state = State.from_problem(_transport())
    assert state.fluents[("fuel", "truck")] == 100.0
    assert ("at", "truck", "a") in state


def test_state_equality_includes_fluents():
    a = State([("p",)], {("f",): 1.0})
    b = State([("p",)], {("f",): 1.0})
    c = State([("p",)], {("f",): 2.0})
    assert a == b and hash(a) == hash(b)
    assert a != c


def test_numeric_precondition_gates_applicability():
    dp = _transport()
    state = State.from_problem(dp)
    drive_ab = next(
        g for g in dp.ground_operator("drive")
        if g.variable_list == {"?v": "truck", "?from": "a", "?to": "b"}
    )
    drive_bc = next(
        g for g in dp.ground_operator("drive")
        if g.variable_list == {"?v": "truck", "?from": "b", "?to": "c"}
    )
    # at a with 100 fuel: a->b (cost 30) is applicable; b->c needs (at truck b).
    assert state.applicable(drive_ab)
    assert not state.applicable(drive_bc)  # truck not at b yet


def test_numeric_effect_decrements_fuel():
    dp = _transport()
    state = State.from_problem(dp)
    drive_ab = next(
        g for g in dp.ground_operator("drive")
        if g.variable_list == {"?v": "truck", "?from": "a", "?to": "b"}
    )
    succ = state.apply(drive_ab)
    assert succ.fluents[("fuel", "truck")] == 70.0  # 100 - 30
    assert ("at", "truck", "b") in succ
    assert ("at", "truck", "a") not in succ
    # original unchanged
    assert state.fluents[("fuel", "truck")] == 100.0


@pytest.mark.parametrize("planner_cls", [BFSPlanner, AStarPlanner, GBFSPlanner])
def test_planners_solve_numeric(planner_cls):
    dp = _transport()
    plan = planner_cls().solve(dp)
    assert plan is not None
    assert len(plan) == 2
    # plan is valid: replay it
    task = GroundedTask(dp)
    state = task.initial
    for action in plan:
        assert state.applicable(action)
        state = state.apply(action)
    assert task.is_goal(state)


def test_insufficient_fuel_is_unsolvable(tmp_path):
    # Only 50 fuel: a->b costs 30 (ok) but then b->c costs 40 -> stuck.
    problem = tmp_path / "p.pddl"
    problem.write_text(
        "(define (problem nt-low) (:domain numeric-transport)\n"
        " (:objects truck - vehicle a b c - location)\n"
        " (:init (at truck a) (road a b) (road b c)\n"
        "        (= (fuel truck) 50) (= (fuel-cost a b) 30) (= (fuel-cost b c) 40))\n"
        " (:goal (at truck c)))"
    )
    dp = DomainProblem(
        os.path.join(CORPUS, "numeric-transport-domain.pddl"), str(problem)
    )
    assert BFSPlanner().solve(dp) is None
