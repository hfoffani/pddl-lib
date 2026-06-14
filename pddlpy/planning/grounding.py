"""Grounding + successor generation — the shared component below the planner.

A ``GroundedTask`` grounds every operator once and exposes a successor
function over ``State``. Blind-search planners use only ``successors`` and
``is_goal``; a future heuristic planner reuses the same grounded action set
without re-deriving it (PRD §5.2).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, List, Tuple

from .state import State

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, Operator


class GroundedTask:
    """A fully grounded planning task derived from a parsed ``DomainProblem``.

    Attributes:
        initial -- the initial ``State``.
        goals   -- the goal atoms (as parsed; checked via ``State.satisfies``).
        actions -- the list of all grounded ``Operator`` instances.
    """

    def __init__(self, domainproblem: "DomainProblem") -> None:
        self.domainproblem = domainproblem
        self.initial: State = State.from_problem(domainproblem)
        self.goals = domainproblem.goals()
        self.actions: List["Operator"] = [
            gop
            for name in domainproblem.operators()
            for gop in domainproblem.ground_operator(name)
        ]

    def successors(self, state: State) -> Iterator[Tuple["Operator", State]]:
        """Yield ``(action, successor_state)`` for every applicable action."""
        for action in self.actions:
            if state.applicable(action):
                yield action, state.apply(action)

    def is_goal(self, state: State) -> bool:
        """True if ``state`` satisfies the goal."""
        return state.satisfies(self.goals)
