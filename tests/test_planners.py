"""Reference planners solve canonical STRIPS problems (Phase 1 acceptance)."""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.planning import (
    AStarPlanner,
    BFSPlanner,
    GBFSPlanner,
    GroundedTask,
    UnsupportedRequirementsError,
    get,
    registry,
)

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(name):
    return DomainProblem(
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


def _execute(dp, plan):
    """Apply a plan from the initial state and return the final State,
    asserting every action was applicable in turn (plan validity)."""
    task = GroundedTask(dp)
    state = task.initial
    for action in plan:
        assert state.applicable(action), "inapplicable action %r" % (action.operator_name,)
        state = state.apply(action)
    return state, task


ALL_PLANNERS = [BFSPlanner, AStarPlanner, GBFSPlanner]


@pytest.mark.parametrize("planner_cls", ALL_PLANNERS)
@pytest.mark.parametrize("problem", ["blocksworld", "gripper"])
def test_planner_solves(planner_cls, problem):
    dp = _dp(problem)
    plan = planner_cls().solve(dp)
    assert plan is not None, "%s found no plan for %s" % (planner_cls.__name__, problem)
    final, task = _execute(dp, plan)
    assert task.is_goal(final), "plan does not reach the goal"


@pytest.mark.parametrize("planner_cls", [BFSPlanner, AStarPlanner])
def test_optimal_planners_agree_on_length(planner_cls):
    # BFS and A* (goal-count, admissible) are optimal for unit costs.
    dp = _dp("gripper")
    plan = planner_cls().solve(dp)
    # Optimal gripper-01 is 5 steps (pick both balls, move, drop both); A*
    # must match BFS's optimal length.
    bfs_len = len(BFSPlanner().solve(dp))
    assert len(plan) == bfs_len == 5


def test_unsolvable_returns_none(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    # goal (q o) can never be achieved: no action adds q.
    domain.write_text(
        "(define (domain d) (:requirements :strips) (:predicates (p ?x) (q ?x))\n"
        " (:action a :parameters (?x) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o) (:init (p o)) (:goal (q o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    assert BFSPlanner().solve(dp) is None


def test_already_solved_returns_empty_plan(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips) (:predicates (p ?x))\n"
        " (:action a :parameters (?x) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o) (:init (p o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    plan = BFSPlanner().solve(dp)
    assert plan is not None and len(plan) == 0


def test_registry_solves():
    # A second planner registers and runs on the same problem without
    # changing the layers below (acceptance criterion).
    dp = _dp("blocksworld")
    for name in ("bfs", "astar", "gbfs"):
        assert name in registry.names()
        plan = get(name).solve(dp)
        assert plan is not None


def test_planner_rejects_unsupported_domain(tmp_path):
    # A domain declaring :disjunctive-preconditions is beyond the STRIPS
    # planners' capabilities -> fail fast.
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips :disjunctive-preconditions)\n"
        " (:predicates (p ?x) (q ?x))\n"
        " (:action a :parameters (?x) :precondition (or (p ?x) (q ?x)) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o) (:init (p o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    with pytest.raises(UnsupportedRequirementsError):
        BFSPlanner().solve(dp)
