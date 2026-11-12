"""#143: :duration-inequalities is a requirement key, and an inequality
bound is not taken as a fixed duration: until the temporal planner can
choose a duration, validate, solve and validate-plan refuse it."""
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
CONSTRAINTS = [
    "(and (>= ?duration 1) (<= ?duration 3))",
    "(<= ?duration 3)",
    # review on #196: an equality next to an inequality is not a duration
    "(and (= ?duration 2) (<= ?duration 0))",
    "(and (<= ?duration 0) (= ?duration 2))",
]
PROBLEM = "(define (problem p) (:domain t) (:objects a) (:init (p a)) (:goal (q a)))"


@pytest.mark.parametrize("constraint", CONSTRAINTS)
@pytest.mark.parametrize("declared", [False, True])
def test_inequality_duration_refused(tmp_path, declared, constraint):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % (" :duration-inequalities" if declared else "", constraint))
    p.write_text(PROBLEM)
    dp = DomainProblem(str(d), str(p))
    assert dp.syntax_errors == 0
    assert [g.duration for g in dp.ground_durative_operator("go")] == [None]  # no bound
    report = diagnose(str(d), str(p))
    assert not report["valid"]
    with pytest.raises(PlannerError):
        get("temporal").solve(dp)
    with pytest.raises(PlannerError):
        validate_plan(dp, parse_plan("0: (go a) [2]\n"))
