"""Plan validation and simulation (roadmap step 3): plan input, verdicts,
failure reports, traces, and what the validator refuses to judge.

The verdicts in tests/validation_cases.py are VAL's (tests/test_oracle.py).
"""
import json
import os

import pytest
from validation_cases import ADL, CASES, TEMPORAL

from pddlpy import DomainProblem
from pddlpy.planning import (
    PlanStep,
    PlanValidationError,
    State,
    load_plan,
    parse_plan,
    plan_from_json,
    simulate,
    validate_plan,
)

IPC = os.path.join(os.path.dirname(__file__), "corpus", "ipc")
GRIPPER = (os.path.join(IPC, "gripper-round-1-strips", "domain.pddl"),
           os.path.join(IPC, "gripper-round-1-strips", "p01.pddl"))


def check(pair, text):
    return validate_plan(DomainProblem(*pair), parse_plan(text))


@pytest.mark.parametrize("pair,text,valid,kind",
                         [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_verdict(pair, text, valid, kind):
    result = check(pair, text)
    assert result.valid is valid
    assert (result.failure and result.failure.kind) == kind


# -- plan input ------------------------------------------------------------

def test_parse_plan_formats():
    text = "; FD header\n(move a b)\n\n0.5: (go x) [2.5] ; trailing\n  (stop)  \n"
    assert parse_plan(text) == [
        PlanStep("move", ("a", "b")),
        PlanStep("go", ("x",), 0.5, 2.5),
        PlanStep("stop", ()),
    ]
    assert str(PlanStep("go", ("x", "y"), 1.0)) == "(go x y)"


@pytest.mark.parametrize("text", ["move a b\n", "()\n", "1.2.3: (a)\n", "(a) (b)\n"])
def test_parse_plan_rejects(text):
    with pytest.raises(PlanValidationError, match="plan line 1"):
        parse_plan(text)


def test_plan_from_json_forms():
    steps = [{"action": "a", "start": 0, "duration": 2}, {"action": "b", "args": ["x"]}]
    expected = [PlanStep("a", (), 0.0, 2.0), PlanStep("b", ("x",))]
    assert plan_from_json(steps) == expected
    assert plan_from_json({"solved": True, "steps": steps}) == expected
    assert plan_from_json([{"action": "a", "time": 1}]) == [PlanStep("a", (), 1.0)]
    bound = plan_from_json([{"action": "pick", "args": {"?y": "c", "?x": "a"}}])[0]
    assert [(b.variable, b) for b in bound.args] == [("?y", "c"), ("?x", "a")]


@pytest.mark.parametrize("data,match", [
    ({"plan": []}, "list of steps"),
    ("x", "list of steps"),
    ([{"args": []}], "step 0 has no 'action'"),
    (["a"], "step 0 has no 'action'"),
    ([{"action": "a", "args": "x"}], "'args' is not"),
    ([{"action": "a", "start": "soon"}], "bad number"),
])
def test_plan_from_json_rejects(data, match):
    with pytest.raises(PlanValidationError, match=match):
        plan_from_json(data)


def test_load_plan_detects_the_form():
    assert load_plan('  [{"action": "a"}]') == [PlanStep("a", ())]
    assert load_plan("(a)") == [PlanStep("a", ())]
    with pytest.raises(PlanValidationError, match="not valid JSON"):
        load_plan("{oops")


def test_solve_output_round_trips():
    """The ``solve`` JSON (args keyed by variable) validates as written."""
    dp = DomainProblem(*ADL)
    data = json.dumps({"steps": [
        {"action": "light", "args": {"?x": "a"}},
        {"action": "pick", "args": {"?y": "c", "?x": "a"}},
        {"action": "inc", "args": {"?x": "c"}},
    ]})
    assert validate_plan(dp, load_plan(data)).valid
    bad = load_plan('[{"action": "pick", "args": {"?x": "a", "?z": "c"}}]')
    failure = validate_plan(dp, bad).failure
    assert failure.kind == "arity" and "?x ?y" in failure.message


# -- failure reports and traces -------------------------------------------

def test_failure_report():
    f = check(GRIPPER, "(pick ball1 rooma left)\n(drop ball2 roomb left)\n").failure
    assert (f.kind, f.step, f.action, f.time) == ("precondition", 2, "(drop ball2 roomb left)", 2.0)
    assert f.unmet == ("(carry ball2 left)", "(at-robby roomb)")
    assert ("carry", "ball1", "left") in f.state
    assert f.message.startswith("step 2 (drop ball2 roomb left) at time 2:")


def test_unmet_renders_conditions():
    f = check(ADL, "(asg a)\n(rd a)\n").failure
    assert f.unmet == ("(> (g) (- (* 2 (f)) (- 1)))",)
    f = check(ADL, "(pick a a)\n").failure
    assert f.unmet == ("(or (lit a) (lamp))", "(not (= a a))")
    assert check(ADL, "(rd a)\n").failure.unmet == ("(g)",)
    f = check(TEMPORAL, "0: (a) [2]\n2.5: (b) [3]\n3: (c) [1]\n").failure
    assert (f.step, f.time, f.unmet) == (2, 5.5, ("(not (s))",))


def test_goal_failure():
    f = check(GRIPPER, "(pick ball1 rooma left)\n").failure
    assert (f.kind, f.step, f.action) == ("goal", None, None)
    assert "(at ball1 roomb)" in f.unmet
    assert f.message == "goal not satisfied after 1 steps"


def test_malformed_step_reports_its_number():
    f = check(ADL, "(asg a)\n(asg a a)\n").failure
    assert (f.kind, f.step) == ("arity", 2)
    assert f.state == State.from_problem(DomainProblem(*ADL))


def test_mutex_report():
    f = check(TEMPORAL, "0: (a) [2]\n1: (k) [1]\n").failure
    assert f.kind == "mutex" and f.unmet == ("(q)",)
    assert "separate them in time" in f.message


def test_simulate_trace():
    sim = simulate(DomainProblem(*TEMPORAL), parse_plan("0: (a) [2]\n2.5: (b) [3]\n"))
    assert sim.executed and sim.failure is None
    assert [(p.time, p.event, p.step, p.action) for p in sim.trace] == [
        (0.0, "start", 1, "(a)"), (2.0, "end", 1, "(a)"),
        (2.5, "start", 2, "(b)"), (5.5, "end", 2, "(b)"),
    ]
    assert ("q",) in sim.trace[1].state and ("r",) not in sim.trace[2].state
    assert sim.state == sim.trace[-1].state and ("r",) in sim.state


def test_simulate_stops_at_failure_and_ignores_goal():
    dp = DomainProblem(*GRIPPER)
    sim = simulate(dp, parse_plan("(pick ball1 rooma left)\n(move rooma roomb)\n"))
    assert sim.executed and len(sim.trace) == 2
    sim = simulate(dp, parse_plan("(pick ball1 rooma left)\n(drop ball1 rooma right)\n"))
    assert not sim.executed and len(sim.trace) == 1
    assert sim.state == sim.trace[0].state


def test_operator_without_precondition(tmp_path):
    domain = tmp_path / "d.pddl"
    domain.write_text("(define (domain d) (:predicates (p) (q))"
                      " (:action go :parameters () :effect (p))"
                      " (:action stop :parameters () :precondition (and (p) (not (q)))"
                      "  :effect (q)))")
    problem = tmp_path / "p.pddl"
    problem.write_text("(define (problem p) (:domain d) (:init) (:goal (q)))")
    dp = DomainProblem(str(domain), str(problem))
    dp.domain.operators["stop"].precondition_tree = None  # the legacy flat form
    assert validate_plan(dp, parse_plan("(go)\n(stop)\n")).valid
    assert validate_plan(dp, parse_plan("(stop)\n")).failure.unmet == ("(p)",)
    assert validate_plan(dp, parse_plan("(go)\n(stop)\n(stop)\n")).failure.unmet == ("(not (q))",)
    assert validate_plan(dp, parse_plan("1: (go)\n1: (stop)\n")).failure.kind == "precondition"
    assert validate_plan(dp, parse_plan("1: (go)\n2: (go)\n2: (stop)\n")).failure.kind == "mutex"


# -- refusals --------------------------------------------------------------

def _pair(tmp_path, domain, problem):
    (tmp_path / "d.pddl").write_text(domain)
    (tmp_path / "p.pddl").write_text(problem)
    return DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))


def test_refuses_syntax_errors():
    dp = DomainProblem(os.path.join(IPC, "logistics-round-1-adl", "domain.pddl"),
                       os.path.join(IPC, "logistics-round-1-adl", "p01.pddl"))
    with pytest.raises(PlanValidationError, match="syntax errors"):
        validate_plan(dp, [])


def test_refuses_unsupported_requirements(tmp_path):
    dp = _pair(tmp_path, "(define (domain d) (:requirements :strips :timed-initial-literals)"
               " (:predicates (p)) (:action a :parameters () :effect (p)))",
               "(define (problem p) (:domain d) (:init) (:goal (p)))")
    with pytest.raises(PlanValidationError, match="timed-initial-literals"):
        simulate(dp, [])


def test_refuses_non_conjunctive_goals():
    dp = DomainProblem(os.path.join(IPC, "elevator-adl-full-typed", "domain.pddl"),
                       os.path.join(IPC, "elevator-adl-full-typed", "p01.pddl"))
    with pytest.raises(PlanValidationError, match="#138"):
        validate_plan(dp, [])


@pytest.mark.parametrize("da", [
    ":duration (<= ?duration 2) :condition (at start (p)) :effect (at end (q))",
    ":duration (and (>= ?duration 1) (<= ?duration 2)) :condition (at start (p))"
    " :effect (at end (q))",
    ":duration (at end (= ?duration 2)) :condition (at start (p)) :effect (at end (q))",
    ":duration (= ?duration (f)) :condition (at start (p)) :effect (at end (q))",
    ":duration (= ?duration 2) :condition (at start (> (f) 0)) :effect (at end (q))",
    ":duration (= ?duration 2) :condition (forall (?x) (at start (p))) :effect (at end (q))",
    ":duration (= ?duration 2) :condition (preference x (at start (p)))"
    " :effect (at end (q))",
    ":duration (= ?duration 2) :condition (at start (p)) :effect (at end (increase (f) 1))",
    ":duration (= ?duration 2) :condition (at start (p))"
    " :effect (at end (when (p) (q)))",
    ":duration (= ?duration 2) :condition (at start (p))"
    " :effect (and (at end (q)) (forall (?x) (at end (p))))",
])
def test_refuses_durative_actions_the_model_does_not_capture(tmp_path, da):
    dp = _pair(tmp_path, "(define (domain d) (:requirements :durative-actions)"
               " (:predicates (p) (q)) (:functions (f)) (:durative-action a :parameters ()"
               " %s))" % da,
               "(define (problem p) (:domain d) (:init (p)) (:goal (q)))")
    assert not dp.domain.durative_operators["a"].simple
    with pytest.raises(PlanValidationError, match="#139"):
        validate_plan(dp, parse_plan("0: (a) [2]\n"))


def test_simple_durative_actions_and_goals_are_flagged(tmp_path):
    dp = _pair(tmp_path, "(define (domain d) (:requirements :durative-actions)"
               " (:predicates (p) (q)) (:durative-action a :parameters ()"
               " :duration (= ?duration 2) :condition () :effect ())"
               " (:durative-action b :parameters () :duration (= ?duration 1)"
               " :condition (at start (and (p) (not (q)))) :effect (at end (q))))",
               "(define (problem p) (:domain d) (:init (p)) (:goal (and (p) (and (p)))))")
    assert dp.domain.durative_operators["a"].simple
    assert dp.domain.durative_operators["b"].simple
    assert dp.problem.simple_goal
    assert next(dp.ground_durative_operator("a")).simple
    assert validate_plan(dp, parse_plan("0: (a) [2]\n")).valid
