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
    atom_tuple,
    get,
    registry,
)
from pddlpy.planning.search import max_goal_adds

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
    # BFS and A* (admissible heuristic, #217) are optimal for unit costs.
    dp = _dp("gripper")
    plan = planner_cls().solve(dp)
    # Optimal gripper-01 is 5 steps (pick both balls, move, drop both); A*
    # must match BFS's optimal length.
    bfs_len = len(BFSPlanner().solve(dp))
    assert len(plan) == bfs_len == 5


def _pair(tmp_path, domain, problem):
    (tmp_path / "d.pddl").write_text(domain)
    (tmp_path / "p.pddl").write_text(problem)
    return DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))


# One action adds every goal atom: plain goal-count overestimates (#217).
_MULTI_GOAL = """(define (domain gc) (:requirements :strips)
 (:predicates (g1) (g2) (g3) (ready))
 (:action prep :parameters () :precondition () :effect (ready))
 (:action finish :parameters () :precondition (ready) :effect (and (g1) (g2) (g3)))
 (:action a1 :parameters () :precondition () :effect (g1))
 (:action a2 :parameters () :precondition (g1) :effect (g2))
 (:action a3 :parameters () :precondition (g2) :effect (g3)))"""
_MULTI_GOAL_PROBLEM = "(define (problem p) (:domain gc) (:init) (:goal (and (g1) (g2) (g3))))"


def test_astar_optimal_when_one_action_adds_several_goals(tmp_path):
    dp = _pair(tmp_path, _MULTI_GOAL, _MULTI_GOAL_PROBLEM)
    plan = AStarPlanner().solve(dp)
    assert [op.operator_name for op in plan] == ["prep", "finish"]


def test_max_goal_adds_counts_conditional_adds(tmp_path):
    dp = _pair(tmp_path, """(define (domain c) (:requirements :strips :conditional-effects)
 (:predicates (g1) (g2) (on))
 (:action on :parameters () :precondition () :effect (on))
 (:action both :parameters () :precondition () :effect (and (g1) (when (on) (g2))))
 (:action a1 :parameters () :precondition () :effect (g1))
 (:action a2 :parameters () :precondition (g1) :effect (g2)))""",
        "(define (problem p) (:domain c) (:init (on)) (:goal (and (g1) (g2))))")
    task = GroundedTask(dp)
    goals = frozenset(atom_tuple(a) for a in task.goals)
    assert max_goal_adds(task, goals) == 2
    assert len(AStarPlanner().solve(dp)) == 1


def test_max_goal_adds_with_derived_predicates_is_every_goal(tmp_path):
    dp = _pair(tmp_path, """(define (domain dr) (:requirements :strips :derived-predicates)
 (:predicates (b) (g1) (g2))
 (:derived (g1) (b)) (:derived (g2) (b))
 (:action set :parameters () :precondition () :effect (b)))""",
        "(define (problem p) (:domain dr) (:init) (:goal (and (g1) (g2))))")
    task = GroundedTask(dp)
    goals = frozenset(atom_tuple(a) for a in task.goals)
    assert max_goal_adds(task, goals) == 2
    assert len(AStarPlanner().solve(dp)) == 1


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
    # ADL is now supported (#10); :durative-actions is still beyond the blind
    # planners' capabilities -> fail fast.
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips :durative-actions)\n"
        " (:predicates (p ?x) (q ?x))\n"
        " (:action a :parameters (?x) :precondition (or (p ?x) (q ?x)) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o) (:init (p o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    with pytest.raises(UnsupportedRequirementsError):
        BFSPlanner().solve(dp)
