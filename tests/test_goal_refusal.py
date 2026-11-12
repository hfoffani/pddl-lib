"""#138 stopgap: goals other than a conjunction of positive atoms are
misread by the model, so solve, validate and validate-plan refuse them
instead of answering for a different goal."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import UnsupportedRequirementsError, get

DOMAIN = ("(define (domain t) (:requirements :adl :numeric-fluents)"
          " (:predicates (p ?x) (q ?x) (r ?x)) (:functions (f))"
          " (:action go :parameters (?x) :precondition (p ?x)"
          "  :effect (and (q ?x) (not (p ?x)) (increase (f) 1))))")
PROBLEM = ("(define (problem p) (:domain t) (:objects a)"
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
    "(imply (p a) (q a))",
    "(exists (?x) (q ?x))",
    "(forall (?x) (q ?x))",
    "(>= (f) 2)",
    "(and (q a) (>= (f) 1))",
])
@pytest.mark.parametrize("planner", ["bfs", "astar", "temporal"])
def test_non_conjunctive_goal_refused(tmp_path, goal, planner):
    d, p = _pair(tmp_path, goal)
    with pytest.raises(UnsupportedRequirementsError, match="#138"):
        get(planner).solve(DomainProblem(d, p))
    if planner == "bfs":
        issues = diagnose(d, p)["issues"]
        assert ("error", "unsupported") in {(i["severity"], i["check"]) for i in issues}
        # quantified variables are not reported as unknown objects
        assert "unknown_object" not in {i["check"] for i in issues}


@pytest.mark.parametrize("goal", ["(q a)", "(and (q a))", "(and)"])
def test_positive_conjunction_still_solved(tmp_path, goal):
    d, p = _pair(tmp_path, goal)
    assert get("bfs").solve(DomainProblem(d, p)) is not None
    assert diagnose(d, p)["valid"]
