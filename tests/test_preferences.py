"""PDDL 3.0 goal preferences (#201): parsed apart from the hard goal, and
the metric over (is-violated ...) minimized by ucs."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import UnsupportedRequirementsError, atom_tuple, get
from pddlpy.planning.validation import parse_plan, validate_plan

# a robot at a; visiting b costs 1, visiting c costs 5 (via b: 1 + 1)
DOMAIN = ("(define (domain v) (:requirements :strips :preferences :action-costs)"
          " (:predicates (at ?x) (link ?x ?y) (seen ?x))"
          " (:functions (total-cost) (cost ?x ?y))"
          " (:action go :parameters (?x ?y) :precondition (and (at ?x) (link ?x ?y))"
          "  :effect (and (not (at ?x)) (at ?y) (seen ?y) (increase (total-cost) (cost ?x ?y)))))")
PROBLEM = ("(define (problem v) (:domain v) (:objects a b c)"
           " (:init (at a) (link a b) (link b c) (= (cost a b) 1) (= (cost b c) 1)"
           "  (= (total-cost) 0))"
           " (:goal (and %s))"
           " (:metric minimize %s))")


def _dp(tmp_path, goal, metric):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM % (goal, metric))
    return DomainProblem(str(d), str(p)), str(d), str(p)


def test_preferences_are_apart_from_the_hard_goal(tmp_path):
    dp, d, p = _dp(tmp_path, "(seen b) (preference pc (seen c))",
                   "(+ (total-cost) (* 10 (is-violated pc)))")
    assert dp.syntax_errors == 0
    assert {atom_tuple(a) for a in dp.goals()} == {("seen", "b")}
    (pref,) = dp.problem.preferences
    assert pref.name == "pc" and repr(pref) == "(preference pc ('seen', 'c'))"
    assert dp.metric() == ("minimize", "(+ (total-cost) (* 10 (is-violated pc)))")
    assert dp.problem.metric_form == {"total-cost": 1.0, "is-violated pc": 10.0}
    assert diagnose(d, p)["valid"]


@pytest.mark.parametrize("weight, plan", [
    (10, ["go a b", "go b c"]),  # violating pc costs more than reaching c
    (0.5, ["go a b"]),           # reaching c costs more than violating pc
])
def test_ucs_minimizes_cost_plus_violations(tmp_path, weight, plan):
    dp, _, _ = _dp(tmp_path, "(seen b) (preference pc (seen c))",
                   "(+ (total-cost) (* %s (is-violated pc)))" % weight)
    found = get("ucs").solve(dp)
    assert [" ".join([n] + list(b.values())) for n, b in found.action_names()] == plan
    # preferences never make a plan invalid
    assert validate_plan(dp, parse_plan("(go a b)\n")).valid


def test_quantified_preference_counts_each_violated_instance(tmp_path):
    """(forall (?x) (preference p (seen ?x))): a, never seen, is one
    violation in every plan; b and c each cost 3 if not seen."""
    dp, _, _ = _dp(tmp_path, "(forall (?x) (preference p (seen ?x)))",
                   "(+ (total-cost) (* 3 (is-violated p)))")
    assert len(dp.problem.preferences[0].ground(dp)) == 3
    found = get("ucs").solve(dp)
    assert len(found) == 2  # cost 2 + 3 (a) beats 0 + 9 and 1 + 6


def test_maximize_and_other_linear_forms(tmp_path):
    dp, _, _ = _dp(tmp_path, "(preference pc (seen c)) (preference pb (seen b))",
                   "(- 12 (+ (total-cost) (* (is-violated pc) 4) (/ (is-violated pb) 2)))")
    assert dp.problem.metric_form == {
        "": 12.0, "total-cost": -1.0, "is-violated pc": -4.0, "is-violated pb": -0.5}
    with pytest.raises(UnsupportedRequirementsError, match="must not reward"):
        get("ucs").solve(dp)  # minimize: the signs make no sense
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    p.write_text(p.read_text().replace(":metric minimize", ":metric maximize"))
    found = get("ucs").solve(DomainProblem(str(d), str(p)))
    assert len(found) == 2


@pytest.mark.parametrize("metric", [
    "(* (total-cost) (is-violated pc))",  # not linear
    "(+ (fuel) (is-violated pc))",        # another fluent
    "(total-time)",
    "(/ (is-violated pc) (total-cost))",
])
def test_non_linear_metric_is_refused(tmp_path, metric):
    dp, _, _ = _dp(tmp_path, "(preference pc (seen c))", metric)
    assert dp.problem.metric_form is None
    with pytest.raises(UnsupportedRequirementsError, match="linear"):
        get("ucs").solve(dp)


def test_metric_forms_without_preferences(tmp_path):
    dp, _, _ = _dp(tmp_path, "(seen b)", "(* 2 3 (- (total-cost)))")
    assert dp.problem.metric_form == {"total-cost": -6.0}
    dp, _, _ = _dp(tmp_path, "(seen b)", "(* 2 3)")
    assert dp.problem.metric_form == {"": 6.0}


def test_no_metric_and_unnamed_preferences(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text("(define (problem v) (:domain v) (:objects a b c)"
                 " (:init (at a) (link a b) (= (cost a b) 1) (= (total-cost) 0))"
                 " (:goal (and (seen b) (preference (seen c)))))")
    dp = DomainProblem(str(d), str(p))
    assert dp.problem.preferences[0].name is None
    assert len(get("ucs").solve(dp)) == 1  # no metric: the preference weighs nothing


@pytest.mark.parametrize("planner", ["bfs", "astar", "gbfs"])
def test_other_planners_refuse_preferences(tmp_path, planner):
    dp, _, _ = _dp(tmp_path, "(preference pc (seen c))", "(is-violated pc)")
    with pytest.raises(UnsupportedRequirementsError, match="ucs"):
        get(planner).solve(dp)


def test_unreachable_hard_goal_has_no_plan(tmp_path):
    dp, _, _ = _dp(tmp_path, "(link c a) (preference pc (seen c))",
                   "(+ (total-cost) (is-violated pc))")
    assert get("ucs").solve(dp) is None
