"""Happening semantics of the plan validator that the probes in
tests/validation_cases.py leave open (found by mutation testing)."""
from types import SimpleNamespace

from pddlpy import DomainProblem
from pddlpy.planning import parse_plan, simulate, validate_plan
from pddlpy.planning.validation import TOLERANCE, _happenings

DOMAIN = """(define (domain s)
 (:requirements :strips :adl :fluents)
 (:predicates (a) (b) (x) (q) (lamp) (r))
 (:functions (f) (g) (h))
 (:action dela :parameters () :precondition (and) :effect (not (a)))
 (:action delb :parameters () :precondition (and) :effect (not (b)))
 (:action setx :parameters () :precondition (and) :effect (x))
 (:action needx :parameters () :precondition (x) :effect (r))
 (:action other :parameters () :precondition (and) :effect (lamp))
 (:action inc :parameters () :precondition (and) :effect (increase (h) 1))
 (:action dec :parameters () :precondition (and) :effect (decrease (h) 1))
 (:action asg :parameters () :precondition (and) :effect (assign (g) 2))
 (:action notq :parameters () :precondition (not (q)) :effect (r))
 (:action addq :parameters () :precondition (and) :effect (q))
 (:action cmp :parameters () :precondition (> (h) (g)) :effect (r))
 (:action guard :parameters () :precondition (a)
   :effect (when (b) (r)))
 (:action gnum :parameters () :precondition (and)
   :effect (when (> (g) 0) (r)))
 (:action rhs :parameters () :precondition (and) :effect (increase (h) (g)))
 (:action twoguards :parameters () :precondition (and)
   :effect (and (when (> (f) 0) (r)) (when (lamp) (q))))
 (:action hguard :parameters () :precondition (> (h) 0)
   :effect (when (> (g) 0) (r)))
 (:action asgh :parameters () :precondition (and) :effect (assign (h) 2))
 (:action two :parameters () :precondition (and (q) (> (f) (g))) :effect (r)))"""


def _dp(tmp_path, init="(a) (b) (= (h) 5) (= (g) 1)", goal="(r)", extra=""):
    (tmp_path / "d.pddl").write_text(DOMAIN)
    (tmp_path / "p.pddl").write_text(
        "(define (problem s1) (:domain s) (:init %s) (:goal %s) %s)" % (init, goal, extra))
    return DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))


def _run(dp, text):
    return simulate(dp, parse_plan(text))


def test_deletes_of_one_happening_all_apply(tmp_path):
    sim = _run(_dp(tmp_path), "0: (dela)\n0: (delb)\n")
    assert sim.failure is None
    assert not {("a",), ("b",)} & sim.state.atoms


def test_happenings_group_within_a_tenth_of_the_tolerance():
    parts = [SimpleNamespace(time=t) for t in (1.0, 1.0 + TOLERANCE / 20, 1.0 + TOLERANCE, 2.0)]
    assert [[p.time for p in h] for h in _happenings(parts)] == [
        [1.0, 1.0 + TOLERANCE / 20], [1.0 + TOLERANCE], [2.0]]


def test_mutex_blames_the_later_step(tmp_path):
    failure = _run(_dp(tmp_path), "0: (setx)\n0: (needx)\n0: (other)\n").failure
    assert failure.kind == "precondition"  # needx reads x before setx adds it
    failure = _run(_dp(tmp_path, init="(x) (a) (b)"), "0: (setx)\n0: (needx)\n0: (other)\n").failure
    assert failure.message == (
        "step 1 (setx) at time 0: interferes with step 2 (needx) over (x) "
        "(separate them in time)")


def test_increase_and_decrease_accumulate(tmp_path):
    sim = _run(_dp(tmp_path), "0: (inc)\n0: (dec)\n")
    assert sim.failure is None and sim.state.fluents[("h",)] == 5


def test_negative_precondition_is_a_read(tmp_path):
    failure = _run(_dp(tmp_path), "0: (notq)\n0: (addq)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(q)",))


def test_both_sides_of_a_comparison_are_reads(tmp_path):
    failure = _run(_dp(tmp_path), "0: (cmp)\n0: (asg)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(g)",))


def test_a_fired_guard_adds_to_the_precondition_reads(tmp_path):
    failure = _run(_dp(tmp_path), "0: (guard)\n0: (dela)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(a)",))
    failure = _run(_dp(tmp_path), "0: (guard)\n0: (delb)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(b)",))


def test_a_numeric_guard_is_a_read(tmp_path):
    failure = _run(_dp(tmp_path), "0: (gnum)\n0: (asg)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(g)",))


def test_an_effect_expression_is_a_read(tmp_path):
    failure = _run(_dp(tmp_path), "0: (rhs)\n0: (asg)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(g)",))


def test_every_guard_must_have_its_fluents(tmp_path):
    failure = _run(_dp(tmp_path), "(twoguards)\n").failure
    assert (failure.kind, failure.unmet) == ("undefined-fluent", ("(f)",))


def test_precondition_and_guard_fluents_are_both_reads(tmp_path):
    failure = _run(_dp(tmp_path), "0: (hguard)\n0: (asgh)\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(h)",))


def test_unmet_precondition_lists_every_undefined_fluent(tmp_path):
    failure = _run(_dp(tmp_path, init="(a) (q)"), "(two)\n").failure
    assert failure.message == (
        "step 1 (two) at time 1: preconditions not satisfied; no value for (f), (g)")


def test_positive_timed_literal_does_not_delete(tmp_path):
    dp = _dp(tmp_path, init="(a) (b) (at 2 (x))")
    assert _run(dp, "2: (setx)\n").failure is None


def test_timed_literals_in_the_trace(tmp_path):
    dp = _dp(tmp_path, init="(a) (b) (at 1 (not (a))) (at 2 (x))")
    sim = _run(dp, "3: (needx)\n")
    assert [(t.time, t.event, t.step, t.action) for t in sim.trace] == [
        (1.0, "til", 0, "(at 1 (not (a)))"), (2.0, "til", 0, "(at 2 (x))"),
        (3.0, "action", 1, "(needx)")]
    assert ("a",) not in sim.state.atoms


def test_goal_with_an_undefined_fluent(tmp_path):
    failure = validate_plan(_dp(tmp_path, goal="(> (f) 0)"), []).failure
    assert failure == ("goal", "goal not satisfied after 0 steps; no value for (f)",
                       None, None, None, ("(> (f) 0)",), failure.state)
    for word in ("and", "or"):
        goal = "(%s (< (f) 1) (a))" % word
        failure = validate_plan(_dp(tmp_path, goal=goal), []).failure
        assert failure.message == "goal not satisfied after 0 steps; no value for (f)"
        assert failure.unmet == (goal,)
    failure = validate_plan(_dp(tmp_path, init="", goal="(> (f) (g))"), []).failure
    assert failure.message == "goal not satisfied after 0 steps; no value for (f), (g)"


def test_preference_with_an_undefined_fluent(tmp_path):
    dp = _dp(tmp_path, goal="(and (a) (preference p1 (> (f) 0)) (preference p2 (> (g) (h))))",
             init="(a) (b)",
             extra="(:metric minimize (+ (is-violated p1) (is-violated p2)))")
    result = validate_plan(dp, [])
    assert result.valid is False and result.simulation is not None
    assert result.failure == (
        "goal", "preferences read fluents with no value: (f), (g), (h)",
        None, None, None, ("(f)", "(g)", "(h)"), result.simulation.state)


def test_quantified_preference_is_grounded(tmp_path):
    (tmp_path / "d.pddl").write_text(DOMAIN)
    (tmp_path / "p.pddl").write_text(
        "(define (problem s1) (:domain s) (:objects o1) (:init (a))"
        " (:goal (and (a) (preference p1 (forall (?o) (> (f) 0)))))"
        " (:metric minimize (is-violated p1)))")
    dp = DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))
    assert validate_plan(dp, []).failure.unmet == ("(f)",)


TEMPORAL = """(define (domain t)
 (:requirements :strips :durative-actions :derived-predicates :fluents)
 (:predicates (q) (d) (r))
 (:functions (f))
 (:derived (d) (> (f) 0))
 (:durative-action nq :parameters () :duration (= ?duration 2)
   :condition (at start (not (q))) :effect (at end (r)))
 (:durative-action aq :parameters () :duration (= ?duration 2)
   :condition (and) :effect (at start (q)))
 (:durative-action od :parameters () :duration (= ?duration 2)
   :condition (over all (not (d))) :effect (at end (r))))"""


def _temporal(tmp_path, init=""):
    (tmp_path / "d.pddl").write_text(TEMPORAL)
    (tmp_path / "p.pddl").write_text(
        "(define (problem t1) (:domain t) (:init %s) (:goal (r)))" % init)
    return DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))


def test_durative_negative_condition_is_a_read(tmp_path):
    failure = _run(_temporal(tmp_path), "0: (nq) [2]\n0: (aq) [2]\n").failure
    assert (failure.kind, failure.unmet) == ("mutex", ("(q)",))


def test_over_all_on_an_undefined_derived_atom(tmp_path):
    dp = _temporal(tmp_path)
    failure = _run(dp, "0: (od) [2]\n").failure
    assert failure[:6] == (
        "undefined-fluent",
        "step 1 (od) at time 0: over all conditions read fluents with no value",
        1, "(od)", 0.0, ("(d)",))
    assert failure.state is not None
