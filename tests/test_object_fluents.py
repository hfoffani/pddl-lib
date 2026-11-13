"""#211: object fluents (PDDL 3.1) parse, and are refused until modeled."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, get
from pddlpy.planning.validation import validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips :typing :equality%s)"
          " (:types truck location) (:predicates (at ?t - truck ?l - location) (p))"
          " (:functions %s)"
          " (:action go :parameters (?t - truck ?l - location)"
          "  :precondition %s :effect %s))")
PROBLEM = ("(define (problem q) (:domain t) (:objects t1 - truck l1 l2 - location)"
           " (:init %s) (:goal (p)))")
NUMERIC = "(fuel ?t - truck) - number"
OBJECT = "(loc ?t - truck) - location"

CASES = [
    # (functions, precondition, effect, init): each uses an object fluent
    (OBJECT, "(and)", "(p)", ""),
    (NUMERIC, "(at ?t (loc ?t))", "(p)", ""),
    (NUMERIC, "(= (loc ?t) ?l)", "(p)", ""),
    (NUMERIC, "(and)", "(and (p) (assign (loc ?t) ?l))", ""),
    (NUMERIC, "(and)", "(and (p) (assign (loc ?t) undefined))", ""),
    (NUMERIC, "(and)", "(p)", "(= (loc t1) l1)"),
]


def _pair(tmp_path, functions, pre, eff, init, declared):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % (" :object-fluents" if declared else "", functions, pre, eff))
    p.write_text(PROBLEM % init)
    return str(d), str(p)


@pytest.mark.parametrize("functions, pre, eff, init", CASES)
@pytest.mark.parametrize("declared", [False, True])
def test_object_fluents_parse_and_are_refused(tmp_path, declared, functions, pre, eff, init):
    d, p = _pair(tmp_path, functions, pre, eff, init, declared)
    dp = DomainProblem(d, p)
    assert dp.syntax_errors == 0
    with pytest.raises(PlannerError, match="object"):
        get("bfs").solve(dp)
    with pytest.raises(PlannerError, match="object"):
        validate_plan(dp, [])
    assert [i["check"] for i in diagnose(d, p)["issues"]
            if i["severity"] == "error"] == ["unsupported"]


def test_numeric_functions_are_not_object_fluents(tmp_path):
    d, p = _pair(tmp_path, NUMERIC, "(>= (fuel ?t) 0)", "(and (p) (assign (fuel ?t) 1))",
                 "(= (fuel t1) 5)", False)
    dp = DomainProblem(d, p)
    assert not dp.domain.object_fluents and not dp.problem.object_fluents
    assert len(get("bfs").solve(dp)) == 1


def test_object_fluent_in_the_goal(tmp_path):
    d, p = _pair(tmp_path, NUMERIC, "(and)", "(p)", "", False)
    (tmp_path / "p.pddl").write_text(
        (PROBLEM % "").replace("(:goal (p))", "(:goal (at t1 (loc t1)))"))
    dp = DomainProblem(d, p)
    assert dp.syntax_errors == 0 and dp.problem.object_fluents
    with pytest.raises(PlannerError, match="object fluents"):
        get("bfs").solve(dp)
