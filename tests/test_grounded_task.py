"""GroundedTask: shared grounding + successor generation."""
import os

import pytest

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


@pytest.mark.parametrize("name", ["blocks-strips-typed", "elevator-adl-full-typed",
                                  "depots-numeric-automatic", "gripper-round-1-strips"])
def test_indexed_successors_match_testing_every_action(name):
    """The applicability index only skips actions that cannot apply: the
    successors, and their order, are those of testing every action."""
    d = os.path.join(CORPUS, "ipc", name)
    task = GroundedTask(DomainProblem(os.path.join(d, "domain.pddl"), os.path.join(d, "p01.pddl")))
    states, frontier = [], [task.initial]
    while frontier and len(states) < 20:
        s = frontier.pop(0)
        states.append(s)
        frontier.extend(n for _, n in task.successors(s))
    every = range(len(task.actions))
    for s in states:
        brute = [a for a in task.actions if s.applicable(a) and task._defined(a, s)]
        assert [a for a, _ in task.successors(s)] == brute
        assert set(task._candidates(s)) <= set(every)
