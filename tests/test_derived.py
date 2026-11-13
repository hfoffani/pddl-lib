"""#141: (:derived (p ?x) GD) parses (PDDL 2.2). Derived predicates are not
modeled yet, so every entry point refuses them instead of solving or
judging as if the rule were absent."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import UnsupportedRequirementsError, atom_tuple, get
from pddlpy.planning.validation import PlanValidationError, parse_plan, validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips :derived-predicates)"
          " (:predicates (p ?x) (q ?x) (r ?x))"
          " (:derived (r ?x) (and (q ?x) (not (p ?x))))"
          " (:action go :parameters (?x) :precondition (p ?x) :effect (q ?x)))")
PROBLEM = "(define (problem p) (:domain t) (:objects a) (:init (p a)) (:goal (r a)))"


@pytest.fixture
def pair(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM)
    return str(d), str(p)


def test_derived_parses_and_is_kept_apart(pair):
    dp = DomainProblem(*pair)
    assert dp.syntax_errors == 0
    assert dp.domain.derived == ["r"]
    # the rule's atoms land nowhere: the action is unchanged
    (go,) = dp.ground_operator("go")
    assert go.precondition_pos == {("p", "a")} and go.effect_pos == {("q", "a")}
    assert {atom_tuple(a) for a in dp.initialstate()} == {("p", "a")}


@pytest.mark.parametrize("planner", ["bfs", "astar", "temporal"])
def test_derived_refused(pair, planner):
    with pytest.raises(UnsupportedRequirementsError, match="#141"):
        get(planner).solve(DomainProblem(*pair))


def test_derived_reported_and_plan_refused(pair, tmp_path):
    issues = diagnose(*pair)["issues"]
    assert [(i["severity"], i["check"]) for i in issues] == [("error", "unsupported")]
    with pytest.raises(PlanValidationError, match="derived"):
        validate_plan(DomainProblem(*pair), parse_plan("(go a)\n"))
    # undeclared requirement: refused by the model check itself
    undeclared = tmp_path / "u.pddl"
    undeclared.write_text(DOMAIN.replace(" :derived-predicates", ""))
    with pytest.raises(PlanValidationError, match="#141"):
        validate_plan(DomainProblem(str(undeclared), pair[1]), parse_plan("(go a)\n"))
