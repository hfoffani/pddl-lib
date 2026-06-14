"""Grounding + successor generation — the shared component below the planner.

A ``GroundedTask`` grounds every operator once and exposes a successor
function over ``State``. Blind-search planners use only ``successors`` and
``is_goal``; a future heuristic planner reuses the same grounded action set
without re-deriving it (PRD §5.2).
"""
from .state import State


class GroundedTask:
    """A fully grounded planning task derived from a parsed ``DomainProblem``.

    Attributes:
        initial -- the initial ``State``.
        goals   -- the goal atoms (as parsed; checked via ``State.satisfies``).
        actions -- the list of all grounded ``Operator`` instances.
    """

    def __init__(self, domainproblem):
        self.domainproblem = domainproblem
        self.initial = State.from_problem(domainproblem)
        self.goals = domainproblem.goals()
        self.actions = [
            gop
            for name in domainproblem.operators()
            for gop in domainproblem.ground_operator(name)
        ]

    def successors(self, state):
        """Yield ``(action, successor_state)`` for every applicable action."""
        for action in self.actions:
            if state.applicable(action):
                yield action, state.apply(action)

    def is_goal(self, state):
        """True if ``state`` satisfies the goal."""
        return state.satisfies(self.goals)
