"""State + Plan types, including the #21 resolution: an operator's
preconditions can be checked against a State without manual Atom/tuple
casting."""
import os

from pddlpy import DomainProblem
from pddlpy.planning import Plan, State

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _blocksworld():
    return DomainProblem(
        os.path.join(CORPUS, "blocksworld-domain.pddl"),
        os.path.join(CORPUS, "blocksworld-problem.pddl"),
    )


def test_state_is_hashable_and_value_equal():
    s1 = State([("on", "a", "b"), ("clear", "c")])
    s2 = State([("clear", "c"), ("on", "a", "b")])
    assert s1 == s2
    assert hash(s1) == hash(s2)
    assert {s1, s2} == {s1}  # usable in a closed set


def test_from_problem_normalizes_atoms():
    # initialstate() returns Atom objects; State must normalize to tuples.
    dp = _blocksworld()
    state = State.from_problem(dp)
    assert ("handempty",) in state
    assert ("clear", "a") in state
    assert len(state) == 7


def test_applicable_without_manual_casting():
    # #21: precondition_pos (Atoms / tuples) vs state — no manual casting.
    dp = _blocksworld()
    state = State.from_problem(dp)
    pickups = list(dp.ground_operator("pick-up"))
    applicable = [op for op in pickups if state.applicable(op)]
    # a, b and c are all clear, on the table, with an empty hand.
    assert {op.variable_list["?x"] for op in applicable} == {"a", "b", "c"}


def test_apply_produces_successor_state():
    dp = _blocksworld()
    state = State.from_problem(dp)
    pickup_a = next(
        op for op in dp.ground_operator("pick-up") if op.variable_list["?x"] == "a"
    )
    succ = state.apply(pickup_a)
    assert ("holding", "a") in succ
    assert ("ontable", "a") not in succ
    assert ("handempty",) not in succ
    # original state is unchanged (immutability)
    assert ("ontable", "a") in state


def test_satisfies_goal():
    dp = _blocksworld()
    goal_state = State([("on", "a", "b"), ("on", "b", "c"), ("clear", "a")])
    assert goal_state.satisfies(dp.goals())
    assert not State.from_problem(dp).satisfies(dp.goals())


def test_plan_basics():
    dp = _blocksworld()
    pickup_a = next(
        op for op in dp.ground_operator("pick-up") if op.variable_list["?x"] == "a"
    )
    plan = Plan([pickup_a])
    assert len(plan) == 1
    assert plan.cost == 1
    assert plan.action_names() == [("pick-up", {"?x": "a"})]
