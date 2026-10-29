"""Solve with a verdict (roadmap step 3): run a planner, tell "unsolvable"
from "no plan within the limits", and validate the plan found.

``Planner.solve`` keeps its contract (a ``Plan``, or ``None`` when the
search space is exhausted); :func:`solve` wraps it for the CLI and the MCP
server.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, NamedTuple, Optional

from .base import PlannerError, SearchLimitError
from .registry import get
from .state import Plan
from .temporal import TemporalPlan
from .validation import PlanStep, PlanValidationError, validate_plan

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem

    from .state import PlanAction

#: ``SolveResult.status`` values.
SOLVED, UNSOLVABLE, LIMIT = "solved", "unsolvable", "limit"


class SolveResult(NamedTuple):
    """``status`` is ``solved``, ``unsolvable`` (the search space was
    exhausted: no plan exists) or ``limit`` (the search stopped at
    ``max_expansions`` / ``timeout``: nothing proven). ``validated`` says
    whether ``validate_plan`` checked the plan; it cannot on domains it
    refuses (see :mod:`pddlpy.planning.validation`)."""

    status: str
    plan: Optional[Plan]
    validated: bool
    message: str


def _args(dp: "DomainProblem", action: "PlanAction") -> tuple:
    """A grounded action's arguments in its declared parameter order."""
    name = action.operator_name
    table = dp.domain.operators if name in dp.domain.operators else dp.domain.durative_operators
    return tuple(str(action.variable_list[v]) for v in table[name].variable_list)


def plan_steps(dp: "DomainProblem", plan: Plan) -> List[PlanStep]:
    """The steps of a pddlpy ``Plan`` as ``validate_plan`` takes them; a
    ``TemporalPlan`` keeps its start times and durations."""
    if isinstance(plan, TemporalPlan):
        return [PlanStep(str(s.action.operator_name), _args(dp, s.action), s.start, s.duration)
                for s in plan.steps]
    return [PlanStep(str(a.operator_name), _args(dp, a)) for a in plan]


def solve(dp: "DomainProblem", planner: str = "astar",
          max_expansions: Optional[int] = None,
          timeout: Optional[float] = None) -> SolveResult:
    """Run ``planner`` on ``dp`` within the limits and validate its plan.
    Raises ``PlannerError`` if the planner refuses the domain, or if its
    plan fails validation (a pddlpy bug)."""
    limits: Dict[str, Any] = {k: v for k, v in
                              (("max_expansions", max_expansions), ("timeout", timeout))
                              if v is not None}
    try:
        plan = get(planner, **limits).solve(dp)
    except SearchLimitError as exc:
        return SolveResult(LIMIT, None, False, str(exc))
    if plan is None:
        return SolveResult(UNSOLVABLE, None, False, "search space exhausted: no plan exists")
    try:
        result = validate_plan(dp, plan_steps(dp, plan))
    except PlanValidationError as exc:
        return SolveResult(SOLVED, plan, False, "plan not validated: %s" % exc)
    if not result.valid:
        raise PlannerError("%s returned a plan that fails validation: %s"
                           % (planner, result.failure.message))  # type: ignore[union-attr]
    return SolveResult(SOLVED, plan, True, "")
