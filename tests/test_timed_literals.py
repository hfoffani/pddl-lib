"""Timed initial literals (#142): kept out of the initial state with their
time, applied by the temporal planner and by plan validation, refused by
the classical planners."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import UnsupportedRequirementsError, atom_tuple, get
from pddlpy.planning.temporal import TemporalTask
from pddlpy.planning.validation import parse_plan, simulate, validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips :durative-actions%s)"
          " (:predicates (p ?x) (q ?x) (r ?x))"
          " (:durative-action go :parameters (?x) :duration (= ?duration 2)"
          "  :condition (at start (p ?x)) :effect (at end (q ?x)))"
          " (:durative-action hold :parameters (?x) :duration (= ?duration 2)"
          "  :condition (over all (p ?x)) :effect (at end (r ?x))))")
PROBLEM = ("(define (problem p) (:domain t) (:objects a)"
           " (:init (q a) (at 5 (p a)) (at 7.5 (not (q a)))) (:goal %s))")


def _pair(tmp_path, goal="(and (q a) (p a))", declared=False, problem=PROBLEM):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % (" :timed-initial-literals" if declared else ""))
    p.write_text(problem % goal)
    return str(d), str(p)


def test_tils_kept_out_of_initial_state(tmp_path):
    dp = DomainProblem(*_pair(tmp_path))
    assert {atom_tuple(a) for a in dp.initialstate()} == {("q", "a")}
    assert [(t, atom_tuple(a), pos) for t, a, pos in dp.problem.timed_literals] == [
        (5.0, ("p", "a"), True), (7.5, ("q", "a"), False)]


@pytest.mark.parametrize("declared", [False, True])
def test_temporal_waits_for_a_til(tmp_path, declared):
    d, p = _pair(tmp_path, "(and (q a) (p a) (r a))", declared)
    dp = DomainProblem(d, p)
    plan = get("temporal").solve(dp)
    # (q a) is deleted at 7.5, after hold ends: the goal is judged after
    # every timed literal, so go must re-add it later
    assert [(s.action.operator_name, s.start) for s in plan.steps] == [
        ("hold", 5.01), ("go", 7.02)]
    assert validate_plan(dp, parse_plan("5.01: (hold a) [2]\n7.02: (go a) [2]\n")).valid
    assert validate_plan(dp, parse_plan("5.01: (hold a) [2]\n")).failure.unmet == ("(q a)",)
    assert diagnose(d, p)["valid"]
    with pytest.raises(UnsupportedRequirementsError, match="temporal planner.*#142"):
        get("bfs").solve(dp)


def test_til_inside_an_action_breaks_its_invariant(tmp_path):
    """(p a) holds only from 1 to 3: hold [2] must fit inside that window."""
    problem = ("(define (problem p) (:domain t) (:objects a)"
               " (:init (at 1 (p a)) (at 3 (not (p a)))) (:goal %s))")
    d, p = _pair(tmp_path, "(r a)", problem=problem)
    dp = DomainProblem(d, p)
    # the earliest start, 1.01, ends at 3.01: (p a) is gone at 3
    assert get("temporal").solve(dp) is None
    failure = validate_plan(dp, parse_plan("1.5: (hold a) [2]\n")).failure
    assert failure.kind == "invariant" and failure.unmet == ("(p a)",)


def test_til_that_happens_while_an_action_runs(tmp_path):
    problem = ("(define (problem p) (:domain t) (:objects a)"
               " (:init (p a) (at 1 (q a))) (:goal %s))")
    d, p = _pair(tmp_path, "(and (q a) (r a))", problem=problem)
    plan = get("temporal").solve(DomainProblem(d, p))
    assert [(s.action.operator_name, s.start) for s in plan.steps] == [("hold", 0.0)]


def test_step_simultaneous_with_a_til_is_mutex(tmp_path):
    d, p = _pair(tmp_path)
    dp = DomainProblem(d, p)
    failure = validate_plan(dp, parse_plan("5.5: (go a) [2]\n")).failure
    assert failure.kind == "mutex" and failure.step == 1 and failure.unmet == ("(q a)",)
    sim = simulate(dp, parse_plan("5.01: (go a) [2]\n"))
    assert [(t.event, t.action) for t in sim.trace] == [
        ("til", "(at 5 (p a))"), ("start", "(go a)"), ("end", "(go a)"),
        ("til", "(at 7.5 (not (q a)))")]


def test_simultaneous_independent_tils_are_not_mutex(tmp_path):
    problem = ("(define (problem p) (:domain t) (:objects a)"
               " (:init (at 1 (p a)) (at 1 (not (q a)))) (:goal %s))")
    d, p = _pair(tmp_path, "(p a)", problem=problem)
    assert validate_plan(DomainProblem(d, p), []).valid
    assert len(get("temporal").solve(DomainProblem(d, p)).steps) == 0


def test_contradictory_tils_are_mutex(tmp_path):
    """Review on #204: VAL rejects every plan when two literals add and
    delete one atom at the same time."""
    problem = ("(define (problem p) (:domain t) (:objects a)"
               " (:init (at 1 (p a)) (at 1 (not (p a)))) (:goal %s))")
    d, p = _pair(tmp_path, "(p a)", problem=problem)
    dp = DomainProblem(d, p)
    failure = validate_plan(dp, []).failure
    assert failure.kind == "mutex" and failure.unmet == ("(p a)",)
    assert get("temporal").solve(dp) is None
    issues = diagnose(d, p)["issues"]
    assert [(i["severity"], i["check"]) for i in issues] == [("error", "timed_literals")]


def test_start_delayed_into_an_end_window(tmp_path):
    """Review on #204: (p) holds from 5 to 6 and go [2] needs it at its end:
    only a start between 3 and 4 works, neither 0 nor just after 5."""
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text("(define (domain w) (:requirements :strips :durative-actions)"
                 " (:predicates (p) (q)) (:durative-action go :parameters ()"
                 " :duration (= ?duration 2) :condition (at end (p)) :effect (at end (q))))")
    p.write_text("(define (problem w) (:domain w) (:init (at 5 (p)) (at 6 (not (p))))"
                 " (:goal (q)))")
    dp = DomainProblem(str(d), str(p))
    plan = get("temporal").solve(dp)
    (step,) = plan.steps
    assert step.start == pytest.approx(3.01)
    assert validate_plan(dp, parse_plan("3.01: (go) [2]\n")).valid


@pytest.mark.parametrize("tils, starts", [
    # go [0, 2] would end at the literal at 2: it starts at 0.01 instead
    ("(at 2 (r a))", [0.01]),
    # ending at 2.01 would hit the next literal: start at 0.02
    ("(at 2 (r a)) (at 2.01 (r a))", [0.02]),
    # a literal at 0: the first step starts after it
    ("(at 0 (r a))", [0.01]),
])
def test_steps_keep_clear_of_tils(tmp_path, tils, starts):
    problem = ("(define (problem p) (:domain t) (:objects a)"
               " (:init (p a) " + tils + ") (:goal %s))")
    d, p = _pair(tmp_path, "(q a)", problem=problem)
    dp = DomainProblem(d, p)
    plan = get("temporal").solve(dp)
    assert [s.start for s in plan.steps] == pytest.approx(starts)
    assert validate_plan(dp, parse_plan("%g: (go a) [2]\n" % starts[0])).valid


def test_successors_ignore_tils(tmp_path):
    """TemporalTask.successors is the timeless view: (p a) arrives at 5."""
    task = TemporalTask(DomainProblem(*_pair(tmp_path)))
    assert list(task.successors(task.initial)) == []
    assert [a.operator_name for a, _, _ in task.successors(task.fire(task.initial, 0, 5)[0])] == [
        "go", "hold"]


def test_successors_include_instantaneous_steps(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text("(define (domain i) (:requirements :strips :durative-actions)"
                 " (:predicates (p)) (:action flip :parameters () :effect (p)))")
    p.write_text("(define (problem q) (:domain i) (:init (at 1 (p))) (:goal (p)))")
    task = TemporalTask(DomainProblem(str(d), str(p)))
    assert [(a.operator_name, dur) for a, dur, _ in task.successors(task.initial)] == [("flip", 0.0)]
