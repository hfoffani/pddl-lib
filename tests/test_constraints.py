"""#140: (:constraints ...) parses without crashing, and every entry point
refuses it instead of solving or judging as if it were absent."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import UnsupportedRequirementsError, check_modeled, get
from pddlpy.planning.validation import PlanValidationError, parse_plan, validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips) (:predicates (p ?x) (q ?x))"
          " %s (:action go :parameters (?x) :precondition (p ?x) :effect (q ?x)))")
PROBLEM = "(define (problem p) (:domain t) (:objects a) (:init (p a)) (:goal (q a)) %s)"
FORMS = [
    "(always (p a))",
    "(and (sometime (q a)) (at-most-once (p a)) (sometime-before (q a) (p a)))",
    "(forall (?x) (always (not (q ?x))))",
]


def _pair(tmp_path, domain_block="", problem_block=""):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % domain_block)
    p.write_text(PROBLEM % problem_block)
    return str(d), str(p)


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("where", ["domain", "problem"])
def test_constraints_parse_and_are_refused(tmp_path, where, form):
    block = "(:constraints %s)" % form
    d, p = _pair(tmp_path, **{where + "_block": block})
    dp = DomainProblem(d, p)
    # the constraint's atoms land nowhere: only (p a) in init, (q a) in goal
    assert len(dp.goals()) == 1 and len(dp.initialstate()) == 1
    with pytest.raises(UnsupportedRequirementsError, match="#140"):
        check_modeled(dp)
    report = diagnose(d, p)
    assert report["valid"] is False
    assert ("error", "unsupported") in {(i["severity"], i["check"]) for i in report["issues"]}


def test_constraints_refused_by_planners_and_plan_validation(tmp_path):
    d, p = _pair(tmp_path, problem_block="(:constraints (always (p a)))")
    dp = DomainProblem(d, p)
    for planner in ("bfs", "temporal"):
        with pytest.raises(UnsupportedRequirementsError, match="#140"):
            get(planner).solve(dp)
    with pytest.raises(PlanValidationError, match="#140"):
        validate_plan(dp, parse_plan("(go a)\n"))


def test_no_constraints_is_modeled(tmp_path):
    check_modeled(DomainProblem(*_pair(tmp_path)))
