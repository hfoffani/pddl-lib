"""Grounding + successor generation — the shared component below the planner.

A ``GroundedTask`` grounds every operator once and exposes a successor
function over ``State``. Blind-search planners use only ``successors`` and
``is_goal``; a future heuristic planner reuses the same grounded action set
without re-deriving it (PRD §5.2).
"""
from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Tuple

from pddlpy.pddl import holds3

from .relaxed import needed_atoms
from .state import State, atom_tuple, goal_holds

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, Operator

    from .state import GroundAtom


class GroundedTask:
    """A fully grounded planning task derived from a parsed ``DomainProblem``.

    Attributes:
        initial -- the initial ``State``.
        goals   -- the goal's positive atoms (as parsed).
        goal    -- the grounded goal condition (#138), checked by ``is_goal``.
        actions -- the list of all grounded ``Operator`` instances.
    """

    def __init__(self, domainproblem: "DomainProblem") -> None:
        self.domainproblem = domainproblem
        self.initial: State = State.from_problem(domainproblem)
        self.goals = domainproblem.goals()
        self.goal = domainproblem.goal_condition()
        # Sorted by operator, then arguments in the order the problem
        # declares its objects: grounding enumerates sets, so its order
        # follows the string hash seed, and the search (successor order, hFF
        # supporters) would differ from run to run.
        declared = {o: i for i, o in enumerate(domainproblem.worldobjects())}
        self.actions: List["Operator"] = [
            gop
            for name in domainproblem.operators()
            for gop in sorted(domainproblem.ground_operator(name), key=lambda op: [
                (declared.get(str(v), len(declared)), str(v)) for v in op.variable_list.values()])
        ]

        self._index: Optional[Tuple[List[int], Dict[GroundAtom, List[int]]]] = None

    def _candidates(self, state: State) -> List[int]:
        """Indices, in order, of the actions that may apply in ``state``.

        Each action is filed under one atom its precondition always needs,
        the one fewest actions need; it is a candidate only when that atom
        holds. Actions that need no atom are always candidates. Built on
        first use."""
        if self._index is None:
            needs = [_needs(a) for a in self.actions]
            freq = collections.Counter(atom for n in needs for atom in n)
            always: List[int] = []
            by_atom: Dict[GroundAtom, List[int]] = {}
            for i, n in enumerate(needs):
                if n:
                    by_atom.setdefault(min(n, key=lambda a: (freq[a], a)), []).append(i)
                else:
                    always.append(i)
            self._index = (always, by_atom)
        always, by_atom = self._index
        found = list(always)
        for atom in state.atoms:
            found.extend(by_atom.get(atom, ()))
        found.sort()
        return found

    def successors(self, state: State) -> Iterator[Tuple["Operator", State]]:
        """Yield ``(action, successor_state)`` for every applicable action,
        in the order of ``actions``."""
        actions = self.actions
        for i in self._candidates(state):
            action = actions[i]
            if state.applicable(action) and self._defined(action, state):
                yield action, state.apply(action).derived(self.domainproblem)

    def _defined(self, action: "Operator", state: State) -> bool:
        """False if the precondition or a conditional-effect guard reads an
        undefined derived atom (#141)."""
        if not self.domainproblem.domain.derived:
            return True
        conditions = [ce.condition for ce in action.conditional_effects]
        if action.precondition is not None:
            conditions.append(action.precondition)
        return all(holds3(c, state.atoms, state.fluents) is not None for c in conditions)

    def is_goal(self, state: State) -> bool:
        """True if ``state`` satisfies the goal."""
        return goal_holds(self.goal, state)


def _needs(action: "Operator") -> "set[GroundAtom]":
    """Atoms ``action``'s precondition needs in every case (a necessary
    condition for ``State.applicable``)."""
    precondition = getattr(action, "precondition", None)
    if precondition is not None:
        return needed_atoms(precondition)
    return {atom_tuple(a) for a in action.precondition_pos}
