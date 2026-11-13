"""Goals beyond a conjunction of positive atoms (#138): not, or, imply,
exists, forall and numeric comparisons are solved and judged."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import get
from pddlpy.planning.validation import parse_plan, validate_plan

DOMAIN = ("(define (domain t) (:requirements :adl :numeric-fluents)"
          " (:predicates (p ?x) (q ?x) (r ?x)) (:functions (f) (g))"
          " (:action go :parameters (?x) :precondition (p ?x)"
          "  :effect (and (q ?x) (not (p ?x)) (increase (f) 1))))")
PROBLEM = ("(define (problem p) (:domain t) (:objects a b)"
           " (:init (p a) (= (f) 0)) (:goal %s))")


def _pair(tmp_path, goal):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM % goal)
    return str(d), str(p)


@pytest.mark.parametrize("goal", [
    "(not (p a))",
    "(and (q a) (not (p a)))",
    "(or (q a) (r a))",
    "(OR (r a) (q a))",
    "(imply (p a) (q a))",
    "(exists (?x) (q ?x))",
    "(forall (?x) (or (q ?x) (= ?x b)))",
    "(and (q a) (>= (f) 1))",
    "(and (= a a) (not (= a b)) (q a))",
])
@pytest.mark.parametrize("planner", ["bfs", "astar", "gbfs", "ucs"])
def test_goal_is_solved(tmp_path, goal, planner):
    d, p = _pair(tmp_path, goal)
    dp = DomainProblem(d, p)
    plan = get(planner).solve(dp)
    assert plan is not None and len(plan) == 1
    if planner == "bfs":
        assert validate_plan(dp, parse_plan("(go a)")).valid
        failure = validate_plan(dp, []).failure
        assert failure.kind == "goal" and failure.unmet
        issues = diagnose(d, p)["issues"]
        assert not issues, issues  # quantified ?x is not an unknown object


@pytest.mark.parametrize("goal", ["(>= (f) 2)", "(and (q a) (r a))", "(exists (?x) (r ?x))"])
def test_unreachable_goal_is_unsolvable(tmp_path, goal):
    d, p = _pair(tmp_path, goal)
    assert get("bfs").solve(DomainProblem(d, p)) is None


def test_goal_failure_lists_the_failing_conjuncts(tmp_path):
    d, p = _pair(tmp_path, "(and (q a) (or (r a) (not (p a))) (>= (f) 3))")
    failure = validate_plan(DomainProblem(d, p), parse_plan("(go a)")).failure
    assert failure.kind == "goal"
    assert failure.unmet == ("(>= (f) 3)",)


def test_goal_reading_an_undefined_fluent_fails(tmp_path):
    """VAL: a comparison over a fluent with no value does not hold."""
    d, p = _pair(tmp_path, "(<= (g) 5)")
    failure = validate_plan(DomainProblem(d, p), []).failure
    assert failure.kind == "goal" and "no value for (g)" in failure.message
    assert failure.unmet == ("(<= (g) 5)",)


@pytest.mark.parametrize("goal", ["(q a)", "(and (q a))", "(and)"])
def test_positive_conjunction_still_solved(tmp_path, goal):
    d, p = _pair(tmp_path, goal)
    assert get("bfs").solve(DomainProblem(d, p)) is not None
    assert diagnose(d, p)["valid"]


def test_free_goal_variable_is_an_unknown_object(tmp_path):
    """Review on #197: only quantified goals bind ?variables."""
    d, p = _pair(tmp_path, "(q ?x)")
    issues = diagnose(d, p)["issues"]
    assert ("error", "unknown_object") in {(i["severity"], i["check"]) for i in issues}


def test_temporal_goal(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text("(define (domain t) (:requirements :durative-actions)"
                 " (:predicates (p) (q))"
                 " (:durative-action go :parameters () :duration (= ?duration 2)"
                 "  :condition (at start (p)) :effect (and (at end (q)) (at end (not (p))))))")
    p.write_text("(define (problem p) (:domain t) (:init (p))"
                 " (:goal (and (not (p)) (or (q) (p)))))")
    plan = get("temporal").solve(DomainProblem(str(d), str(p)))
    assert plan is not None and plan.makespan == 2
