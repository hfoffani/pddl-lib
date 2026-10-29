"""planning.solve (#166): status (solved / unsolvable / limit) and
self-validation of the plan found."""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.planning import (
    LIMIT,
    SOLVED,
    UNSOLVABLE,
    Plan,
    Planner,
    PlannerError,
    PlanStep,
    SearchLimitError,
    get,
    plan_steps,
    register,
    solve,
)

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(domain, problem=None):
    return DomainProblem(os.path.join(CORPUS, "%s-domain.pddl" % domain),
                         os.path.join(CORPUS, "%s-problem.pddl" % (problem or domain)))


@pytest.mark.parametrize("planner", ["bfs", "astar", "gbfs", "ucs"])
def test_solved_and_validated(planner):
    result = solve(_dp("gripper"), planner)
    assert (result.status, result.validated, result.message) == (SOLVED, True, "")
    assert result.plan is not None


def test_temporal_plan_validated():
    result = solve(_dp("temporal-charge"), "temporal")
    assert (result.status, result.validated) == (SOLVED, True)
    assert plan_steps(_dp("temporal-charge"), result.plan) == [
        PlanStep("plug", ("phone",), 0.0, 0.0),
        PlanStep("charge-battery", ("phone",), 0.01, 4.0),
    ]


def test_plan_steps_in_parameter_order():
    dp = _dp("logistics")
    plan = get("bfs").solve(dp)
    for step, action in zip(plan_steps(dp, plan), plan):
        lifted = dp.domain.operators[action.operator_name].variable_list
        assert step.args == tuple(action.variable_list[v] for v in lifted)


def test_unsolvable():
    result = solve(_dp("temporal-weld", "temporal-weld-notorch"), "temporal")
    assert (result.status, result.plan, result.validated) == (UNSOLVABLE, None, False)


@pytest.mark.parametrize("planner", ["bfs", "astar", "temporal"])
def test_max_expansions(planner):
    dp = _dp("temporal-charge" if planner == "temporal" else "gripper")
    result = solve(dp, planner, max_expansions=1)
    assert (result.status, result.plan) == (LIMIT, None)
    assert "stopped after 1 expansions" in result.message
    with pytest.raises(SearchLimitError):
        get(planner, max_expansions=1).solve(dp)


def test_timeout():
    result = solve(_dp("gripper"), "bfs", timeout=0)
    assert result.status == LIMIT and "timeout" in result.message


def test_limits_reset_per_search():
    planner = get("bfs", max_expansions=10_000)
    dp = _dp("gripper")
    assert planner.solve(dp) is not None and planner.solve(dp) is not None


def test_unvalidated_when_the_validator_refuses(tmp_path):
    (tmp_path / "d.pddl").write_text("(define (domain d) (:predicates (p) (q))"
                                     " (:action a :parameters () :effect (and (p) (q))))")
    (tmp_path / "p.pddl").write_text("(define (problem p) (:domain d) (:init)"
                                     " (:goal (or (p) (q))))")
    dp = DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))
    result = solve(dp, "bfs")
    assert result.status == SOLVED
    assert result.validated is False
    assert result.message.startswith("plan not validated:") and "#138" in result.message


class _Liar(Planner):
    """Returns a one-step plan that does not reach the goal."""

    capabilities = frozenset({":strips", ":typing"})

    def solve(self, domainproblem):
        return Plan(list(domainproblem.ground_operator("move"))[:1])


def test_invalid_plan_is_an_error():
    register("liar", _Liar)
    with pytest.raises(PlannerError, match="liar returned a plan that fails validation"):
        solve(_dp("gripper"), "liar")
