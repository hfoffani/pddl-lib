"""#3 action costs: metric capture, action_cost/plan_cost, cost-aware search."""
import os

from pddlpy import DomainProblem
from pddlpy.planning import (
    TOTAL_COST,
    BFSPlanner,
    GroundedTask,
    State,
    UniformCostPlanner,
    action_cost,
    get,
    plan_cost,
    registry,
)

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _travel():
    return DomainProblem(
        os.path.join(CORPUS, "travel-domain.pddl"),
        os.path.join(CORPUS, "travel-problem.pddl"),
    )


def _move(dp, frm, to):
    return next(
        g for g in dp.ground_operator("move")
        if g.variable_list == {"?from": frm, "?to": to}
    )


def test_metric_captured():
    assert _travel().metric() == ("minimize", "(total-cost)")


def test_action_cost_reads_total_cost_increase():
    dp = _travel()
    state = State.from_problem(dp)
    assert action_cost(_move(dp, "a", "b"), state) == 1.0
    assert action_cost(_move(dp, "a", "c"), state) == 5.0


def test_action_cost_defaults_to_one_without_total_cost():
    # blocksworld actions have no total-cost effect -> unit cost.
    dp = DomainProblem(
        os.path.join(CORPUS, "blocksworld-domain.pddl"),
        os.path.join(CORPUS, "blocksworld-problem.pddl"),
    )
    state = State.from_problem(dp)
    op = next(dp.ground_operator("pick-up"))
    assert action_cost(op, state) == 1.0


def test_plan_cost_helper():
    goal_with_cost = State([("at", "c")], {TOTAL_COST: 7.0})
    assert plan_cost(goal_with_cost, [1, 2]) == 7.0
    goal_without = State([("at", "c")])
    assert plan_cost(goal_without, [1, 2, 3]) == 3


def test_ucs_is_cost_optimal():
    dp = _travel()
    plan = UniformCostPlanner().solve(dp)
    route = [b["?to"] for _, b in plan.action_names()]
    assert route == ["b", "c"]   # cheaper 2-hop route
    assert plan.cost == 2.0


def test_bfs_minimizes_actions_not_cost():
    dp = _travel()
    plan = BFSPlanner().solve(dp)
    route = [b["?to"] for _, b in plan.action_names()]
    assert route == ["c"]        # single hop, fewest actions
    assert plan.cost == 5.0      # but its true total-cost is higher


def test_ucs_registered():
    assert "ucs" in registry.names()
    assert isinstance(get("ucs"), UniformCostPlanner)


def test_ucs_plan_is_valid():
    dp = _travel()
    plan = UniformCostPlanner().solve(dp)
    task = GroundedTask(dp)
    state = task.initial
    for action in plan:
        assert state.applicable(action)
        state = state.apply(action)
    assert task.is_goal(state)
    assert state.fluents[TOTAL_COST] == 2.0
