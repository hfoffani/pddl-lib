"""#142 stopgap: timed initial literals stay out of the initial state, are
kept with their time, and every entry point refuses them, whether or not
:timed-initial-literals is declared."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, UnsupportedRequirementsError, atom_tuple, get
from pddlpy.planning.validation import parse_plan, validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips :durative-actions%s)"
          " (:predicates (p ?x) (q ?x))"
          " (:durative-action go :parameters (?x) :duration (= ?duration 2)"
          "  :condition (at start (p ?x)) :effect (at end (q ?x))))")
PROBLEM = ("(define (problem p) (:domain t) (:objects a)"
           " (:init (q a) (at 5 (p a)) (at 7.5 (not (q a)))) (:goal (q a)))")


def _pair(tmp_path, declared=False):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % (" :timed-initial-literals" if declared else ""))
    p.write_text(PROBLEM)
    return str(d), str(p)


def test_tils_kept_out_of_initial_state(tmp_path):
    dp = DomainProblem(*_pair(tmp_path))
    assert {atom_tuple(a) for a in dp.initialstate()} == {("q", "a")}
    assert [(t, atom_tuple(a), pos) for t, a, pos in dp.problem.timed_literals] == [
        (5.0, ("p", "a"), True), (7.5, ("q", "a"), False)]


@pytest.mark.parametrize("declared", [False, True])
def test_tils_refused(tmp_path, declared):
    d, p = _pair(tmp_path, declared)
    dp = DomainProblem(d, p)
    with pytest.raises(UnsupportedRequirementsError, match="#142"):
        get("temporal").solve(dp)
    issues = diagnose(d, p)["issues"]
    assert ("error", "unsupported") in {(i["severity"], i["check"]) for i in issues}
    with pytest.raises(PlannerError):
        validate_plan(dp, parse_plan("0: (go a) [2]\n"))
