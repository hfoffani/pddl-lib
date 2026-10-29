"""#84 temporal planner: schedules durative-action domains under sequential
semantics (start/end events; 'at start', 'over all', 'at end').

The planner enforces the full time-tagged contract that
:class:`~pddlpy.planning.DurativeState` (at-start only) cannot, applies start
effects at the start point and end effects at start+duration, and returns a
:class:`~pddlpy.planning.TemporalPlan` carrying per-step start times, durations
and a makespan.
"""
import os

from pddlpy import DomainProblem
from pddlpy.planning import (
    DurativeState,
    ScheduledAction,
    TemporalPlan,
    TemporalPlanner,
    apply_durative,
    get,
)
from pddlpy.planning.state import State

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(domain, problem):
    return DomainProblem(os.path.join(CORPUS, domain), os.path.join(CORPUS, problem))


def _go():
    return _dp("durative-action-domain.pddl", "durative-action-problem.pddl")


def _weld(problem="temporal-weld-problem.pddl"):
    return _dp("temporal-weld-domain.pddl", problem)


def _charge():
    return _dp("temporal-charge-domain.pddl", "temporal-charge-problem.pddl")


# -- registry / plumbing --------------------------------------------------
def test_registered_as_temporal():
    assert isinstance(get("temporal"), TemporalPlanner)


def test_declares_durative_actions_capability():
    assert ":durative-actions" in TemporalPlanner.capabilities


# -- simple durative schedule (go) ---------------------------------------
def test_go_schedule():
    plan = get("temporal").solve(_go())
    assert plan is not None
    assert plan.makespan == 5.0
    assert plan.action_names() == [("go", {"?from": "a", "?to": "b"})]
    (step,) = plan.steps
    assert (step.start, step.duration, step.end) == (0.0, 5.0, 5.0)
    assert plan.cost == plan.makespan


# -- 'over all' genuinely constrains the plan -----------------------------
def test_over_all_forces_steady_weld():
    dp = _weld()
    plan = get("temporal").solve(dp)
    assert plan is not None
    # steady-weld (makespan 6) is picked over the shorter quick-weld, which an
    # at-start-only checker would (wrongly) accept.
    assert plan.action_names() == [("steady-weld", {"?p": "p1"})]
    assert plan.makespan == 6.0


def test_quick_weld_naive_vs_temporal():
    dp = _weld()
    quick = next(g for g in dp.ground_durative_operator("quick-weld"))
    # An at-start-only view accepts quick-weld ...
    assert DurativeState.from_problem(dp).applicable(quick) is True
    # ... but the temporal planner rejects it: its start effect drops the part,
    # violating its own 'over all (holding)' invariant.
    assert apply_durative(State.from_problem(dp), quick) is None


def test_at_end_condition_unsatisfiable_is_unsolvable():
    # No lit torch: steady-weld's 'at end (torch-lit)' fails, quick-weld
    # self-violates 'over all' -> no schedule.
    assert get("temporal").solve(_weld("temporal-weld-notorch-problem.pddl")) is None


# -- mixed instantaneous + durative --------------------------------------
def test_mixed_instantaneous_and_durative():
    plan = get("temporal").solve(_charge())
    assert plan is not None
    assert plan.makespan == 4.01
    assert plan.action_names() == [
        ("plug", {"?d": "phone"}),
        ("charge-battery", {"?d": "phone"}),
    ]
    plug, charge = plan.steps
    assert (plug.start, plug.duration) == (0.0, 0.0)  # zero-duration step
    # #165: charge needs plug's effect, so it starts SEPARATION later.
    assert (charge.start, charge.duration, charge.end) == (0.01, 4.0, 4.01)


def test_separation_counts_in_the_makespan(tmp_path):
    """#165 review: the search must rank by the makespan the schedule will
    have. Direct (1.005) beats two dependent halves (0.5 + 0.01 + 0.5), though
    the halves have the smaller total duration (1.0)."""
    domain = tmp_path / "d.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :durative-actions)"
        " (:predicates (s) (m) (g))"
        " (:durative-action direct :parameters () :duration (= ?duration 1.005)"
        "  :condition (at start (s)) :effect (at end (g)))"
        " (:durative-action h1 :parameters () :duration (= ?duration 0.5)"
        "  :condition (at start (s)) :effect (at end (m)))"
        " (:durative-action h2 :parameters () :duration (= ?duration 0.5)"
        "  :condition (at start (m)) :effect (at end (g))))"
    )
    problem = tmp_path / "p.pddl"
    problem.write_text("(define (problem p) (:domain d) (:init (s)) (:goal (g)))")
    plan = get("temporal").solve(DomainProblem(str(domain), str(problem)))
    assert [a.operator_name for a in plan.actions] == ["direct"]
    assert plan.makespan == 1.005


def test_temporal_plans_pass_the_validator():
    """#165: the schedule passes validate_plan (VAL's semantics); with the
    two steps at the same time point it would not."""
    from pddlpy.planning import PlanStep, validate_plan
    dp = _charge()
    plan = get("temporal").solve(dp)
    steps = [PlanStep(s.action.operator_name, tuple(s.action.variable_list.values()),
                      s.start, s.duration) for s in plan.steps]
    assert validate_plan(dp, steps).valid
    same_time = [s._replace(time=0.0) for s in steps]
    assert validate_plan(dp, same_time).failure.kind == "precondition"


# -- effect timing: start effects at start, end effects at start+duration --
def test_start_and_end_effect_timing():
    dp = _go()
    state = State.from_problem(dp)
    go_ab = next(
        g
        for g in dp.ground_durative_operator("go")
        if g.variable_list == {"?from": "a", "?to": "b"}
    )
    succ = apply_durative(state, go_ab)
    assert succ is not None
    # start effect removed (at a); end effects added (at b), (visited b).
    assert ("at", "a") not in succ.atoms
    assert {("at", "b"), ("visited", "b")} <= succ.atoms


def test_at_start_condition_gates_application():
    dp = _go()
    state = State.from_problem(dp)  # (at a), (road a b)
    go_ba = next(
        g
        for g in dp.ground_durative_operator("go")
        if g.variable_list == {"?from": "b", "?to": "a"}
    )
    # 'at start (at b)' does not hold in the initial state.
    assert apply_durative(state, go_ba) is None


# -- value types ----------------------------------------------------------
def test_scheduled_action_repr_and_end():
    plan = get("temporal").solve(_go())
    (step,) = plan.steps
    assert isinstance(step, ScheduledAction)
    assert step.end == step.start + step.duration
    assert "go(a, b)" in repr(step)


def test_temporal_plan_repr():
    plan = get("temporal").solve(_go())
    assert isinstance(plan, TemporalPlan)
    text = repr(plan)
    assert "makespan=5" in text
    assert "go(a, b)" in text
