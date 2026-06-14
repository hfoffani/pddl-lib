"""GroundedTask: shared grounding + successor generation."""
import os

from pddlpy import DomainProblem
from pddlpy.planning import GroundedTask, State

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _task(name):
    dp = DomainProblem(
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )
    return GroundedTask(dp)


def test_initial_and_goal():
    task = _task("blocksworld")
    assert isinstance(task.initial, State)
    assert not task.is_goal(task.initial)
    # a state containing the goal atoms satisfies the goal
    assert State([("on", "a", "b"), ("on", "b", "c")]).satisfies(task.goals)


def test_successors_are_applicable():
    task = _task("blocksworld")
    succ = list(task.successors(task.initial))
    # from the all-on-table start, the only applicable actions are pick-ups.
    assert succ, "expected at least one successor"
    assert all(a.operator_name == "pick-up" for a, _ in succ)
    assert {a.variable_list["?x"] for a, _ in succ} == {"a", "b", "c"}
    # each successor state differs from the start
    assert all(s != task.initial for _, s in succ)


def test_grounding_done_once():
    task = _task("gripper")
    # move(4) + pick(8) + drop(8) = 20 grounded actions
    assert len(task.actions) == 20
