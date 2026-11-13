"""#143: :duration-inequalities. Numeric bounds give a duration range: the
temporal planner takes the shortest duration it allows, and plan
validation accepts any duration inside it. Timed or expression bounds are
not modeled and stay refused."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, get
from pddlpy.planning.validation import parse_plan, validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips :durative-actions%s)"
          " (:predicates (p ?x) (q ?x))"
          " (:durative-action go :parameters (?x)"
          "  :duration %s"
          "  :condition (at start (p ?x)) :effect (at end (q ?x))))")
PROBLEM = "(define (problem p) (:domain t) (:objects a) (:init (p a)) (:goal (q a)))"


def _dp(tmp_path, constraint, declared=True):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % (" :duration-inequalities" if declared else "", constraint))
    p.write_text(PROBLEM)
    dp = DomainProblem(str(d), str(p))
    assert dp.syntax_errors == 0
    return dp, str(d), str(p)


@pytest.mark.parametrize("constraint, planned, good, bad", [
    ("(and (>= ?duration 1) (<= ?duration 3))", 1.0, ["1", "2.5", "3"], ["0.5", "4"]),
    ("(>= ?duration 2)", 2.0, ["2", "100"], ["1"]),
    # VAL accepts 0 here (it also accepts negative durations; pddlpy does not)
    ("(<= ?duration 3)", 0.01, ["0.01", "0", "3", "3.0005"], ["4", "-1"]),
    ("(and (>= ?duration 2) (<= ?duration 2))", 2.0, ["2"], ["3"]),
    ("(and (= ?duration 2) (<= ?duration 5))", 2.0, ["2"], ["3"]),
])
@pytest.mark.parametrize("declared", [False, True])
def test_duration_range(tmp_path, declared, constraint, planned, good, bad):
    dp, d, p = _dp(tmp_path, constraint, declared)
    assert diagnose(d, p)["valid"]
    plan = get("temporal").solve(dp)
    assert [s.duration for s in plan.steps] == [planned]
    for duration in good:
        assert validate_plan(dp, parse_plan("0: (go a) [%s]\n" % duration)).valid
    for duration in bad:
        assert validate_plan(dp, parse_plan("0: (go a) [%s]\n" % duration)).failure.kind == "duration"


@pytest.mark.parametrize("constraint", [
    "(and (= ?duration 2) (<= ?duration 0))",
    "(and (<= ?duration 0) (= ?duration 2))",
    "(<= ?duration 0)",
    "(and (>= ?duration 3) (<= ?duration 2))",
])
def test_empty_duration_range(tmp_path, constraint):
    dp, d, p = _dp(tmp_path, constraint)
    assert [i["check"] for i in diagnose(d, p)["issues"]] == ["durative"]
    with pytest.raises(PlannerError):
        get("temporal").solve(dp)
    assert validate_plan(dp, parse_plan("0: (go a) [2]\n")).failure.kind == "duration"


@pytest.mark.parametrize("constraint", [
    # timed leaves, in both orders (review on #196)
    "(and (at start (= ?duration 2)) (<= ?duration 0))",
    "(and (<= ?duration 0) (at start (= ?duration 2)))",
    "(and (= ?duration 2) (at end (<= ?duration 0)))",
    "(at start (= ?duration 2))",
    "()",
])
def test_timed_duration_constraints_refused(tmp_path, constraint):
    dp, d, p = _dp(tmp_path, constraint)
    assert [g.duration for g in dp.ground_durative_operator("go")] == [None]
    assert not diagnose(d, p)["valid"]
    with pytest.raises(PlannerError):
        get("temporal").solve(dp)
    with pytest.raises(PlannerError):
        validate_plan(dp, parse_plan("0: (go a) [2]\n"))


def _solve(tmp_path, domain, problem):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(domain)
    p.write_text(problem)
    dp = DomainProblem(str(d), str(p))
    plan = get("temporal").solve(dp)
    text = "".join("%g: (%s) [%g]\n" % (s.start, s.action.operator_name, s.duration)
                   for s in plan.steps)
    assert validate_plan(dp, parse_plan(text)).valid
    return plan


def test_duration_stretched_to_a_later_timed_literal(tmp_path):
    """Review on #210: p holds until 1 and q from 2, so go must last ~2."""
    plan = _solve(tmp_path,
                  "(define (domain t) (:requirements :strips :durative-actions"
                  " :duration-inequalities :timed-initial-literals) (:predicates (p) (q) (done))"
                  " (:durative-action go :parameters ()"
                  "  :duration (and (>= ?duration 1) (<= ?duration 3))"
                  "  :condition (and (at start (p)) (at end (q))) :effect (at end (done))))",
                  "(define (problem x) (:domain t) (:init (p) (at 1 (not (p))) (at 2 (q)))"
                  " (:goal (done)))")
    assert [(s.start, round(s.duration, 3)) for s in plan.steps] == [(0.0, 2.01)]


def test_duration_kept_apart_from_the_start(tmp_path):
    """Review on #210: a 0.0005 lower bound would merge start and end."""
    plan = _solve(tmp_path,
                  "(define (domain t) (:requirements :strips :durative-actions"
                  " :duration-inequalities) (:predicates (p) (q) (done))"
                  " (:durative-action go :parameters ()"
                  "  :duration (and (>= ?duration 0.0005) (<= ?duration 1))"
                  "  :condition (and (at start (p)) (at end (q)))"
                  "  :effect (and (at start (q)) (at end (done)))))",
                  "(define (problem x) (:domain t) (:init (p)) (:goal (done)))")
    assert [s.duration for s in plan.steps] == [0.01]


def test_delayed_start_with_a_longer_duration(tmp_path):
    """Review on #210: [1, 1.5] must start late and last 1.5 to bridge."""
    plan = _solve(tmp_path,
                  "(define (domain t) (:requirements :strips :durative-actions"
                  " :duration-inequalities :timed-initial-literals) (:predicates (p) (q) (done))"
                  " (:durative-action go :parameters ()"
                  "  :duration (and (>= ?duration 1) (<= ?duration 1.5))"
                  "  :condition (and (at start (p)) (at end (q))) :effect (at end (done))))",
                  "(define (problem x) (:domain t) (:init (p) (at 1 (not (p))) (at 2 (q)))"
                  " (:goal (done)))")
    assert [(round(s.start, 3), s.duration) for s in plan.steps] == [(0.51, 1.5)]


def test_short_duration_before_a_timed_literal(tmp_path):
    """Review on #210: 0.002 already separates start and end; 0.01 would
    cross the literal that breaks the invariant at 0.007."""
    plan = _solve(tmp_path,
                  "(define (domain t) (:requirements :strips :durative-actions"
                  " :duration-inequalities :timed-initial-literals) (:predicates (p) (q) (done))"
                  " (:durative-action go :parameters ()"
                  "  :duration (and (>= ?duration 0.002) (<= ?duration 0.02))"
                  "  :condition (and (at start (p)) (over all (p)) (at end (q)))"
                  "  :effect (and (at start (q)) (at end (done)))))",
                  "(define (problem x) (:domain t) (:init (p) (at 0.007 (not (p))))"
                  " (:goal (done)))")
    assert [s.duration for s in plan.steps] == [0.002]
