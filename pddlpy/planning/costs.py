"""Action-cost helpers (Phase 3).

PDDL action costs are modeled as ``(increase (total-cost) <expr>)`` effects,
typically minimized via ``(:metric minimize (total-cost))``. ``total-cost`` is
just a numeric fluent (Phase 2), so the cost machinery is thin: read the
``total-cost`` increases for per-step cost, and read the accumulated
``total-cost`` fluent for the final plan cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from pddlpy.pddl import Operator
    from .state import GroundAtom, State

#: The reserved cost fluent head.
TOTAL_COST = ("total-cost",)


def action_cost(operator: "Operator", state: "State") -> float:
    """The cost of applying ``operator`` in ``state``.

    Sums the ``(increase (total-cost) expr)`` effects (each ``expr`` evaluated
    in the current state). Actions with no ``total-cost`` effect cost 1.0, so
    cost-aware search degrades gracefully to unit cost.
    """
    total = 0.0
    found = False
    for eff in operator.effect_num:
        if eff.head.head == TOTAL_COST and eff.op == "increase":
            total += eff.expr.value(state.fluents)
            found = True
    return total if found else 1.0


def plan_cost(goal_state: "State", actions: Sequence["Operator"]) -> float:
    """The cost of a found plan: the accumulated ``total-cost`` if the domain
    tracks it, otherwise the number of actions."""
    if TOTAL_COST in goal_state.fluents:
        return goal_state.fluents[TOTAL_COST]
    return len(actions)
