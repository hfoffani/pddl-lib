"""#213: continuous effects (PDDL 2.1) parse, and are refused until modeled."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, get
from pddlpy.planning.validation import validate_plan

DOMAIN = ("(define (domain t) (:requirements :durative-actions :numeric-fluents%s)"
          " (:predicates (p) (q)) (:functions (f) (rate))"
          " (:durative-action a :parameters () :duration (= ?duration 2)"
          "  :condition (at start (>= (f) 0))"
          "  :effect (and (at end (p)) %s)))")
PROBLEM = "(define (problem q) (:domain t) (:init (= (f) 0) (= (rate) 1)) (:goal (p)))"

EFFECTS = [
    "(increase (f) #t)",
    "(increase (f) (* #t 2))",
    "(decrease (f) (* 2 #t))",
    "(increase (f) (* #t (rate)))",
    "(increase (f) (* (- (rate) 1) #t))",
    "(increase (f) 2)",  # untimed: crashed the listener before #213
    "(when (at start (q)) (increase (f) (* #t 2)))",
    "(forall (?x) (increase (f) #t))",
]


def _pair(tmp_path, effect, declared):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % (" :continuous-effects" if declared else "", effect))
    p.write_text(PROBLEM)
    return str(d), str(p)


@pytest.mark.parametrize("effect", EFFECTS)
@pytest.mark.parametrize("declared", [False, True])
def test_continuous_effects_parse_and_are_refused(tmp_path, declared, effect):
    d, p = _pair(tmp_path, effect, declared)
    dp = DomainProblem(d, p)
    assert dp.syntax_errors == 0
    assert dp.domain.durative_operators["a"].continuous
    assert next(iter(dp.ground_durative_operator("a"))).continuous
    match = "continuous-effects" if declared else "continuous effects.*: a"
    for name in ("temporal", "bfs"):
        with pytest.raises(PlannerError, match=match):
            get(name).solve(dp)
    with pytest.raises(PlannerError, match=match):
        validate_plan(dp, [])
    assert [i["check"] for i in diagnose(d, p)["issues"]
            if i["severity"] == "error"] == ["unsupported"]


def test_discrete_effects_are_not_continuous(tmp_path):
    d, p = _pair(tmp_path, "(at end (increase (f) 2))", False)
    dp = DomainProblem(d, p)
    assert dp.syntax_errors == 0
    assert not dp.domain.durative_operators["a"].continuous


@pytest.mark.parametrize("effect", ["(at end (increase (f) #t))",
                                    "(increase (f) (+ #t 2))"])
def test_t_outside_a_continuous_effect_is_a_syntax_error(tmp_path, effect):
    d, p = _pair(tmp_path, effect, False)
    assert DomainProblem(d, p).syntax_errors > 0
