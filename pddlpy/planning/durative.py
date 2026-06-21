"""Durative-action validation and a small applicability state (#23).

The object model already parses and grounds durative actions into
``DurativeAction`` (time-tagged ``at start`` / ``over all`` / ``at end``
conditions and effects, plus a duration). This module adds the *semantic*
layer the reference planners deliberately stop short of:

* :func:`validate_durative_action` — structural checks (well-formed positive
  duration; conditions/effects reference declared predicates and the action's
  own parameters).
* :class:`DurativeState` — a small, dedicated state that answers a single
  question: are a grounded durative action's **``at start``** conditions
  satisfied? This is *not* a temporal planner — there is no timeline, no
  scheduling of ``over all`` / ``at end`` conditions, and no overlap handling.
  Solving durative domains remains out of scope (PRD §3/§5).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Iterator, Optional, Set

from .base import PlannerError
from .state import GroundAtom, atom_tuple

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, DurativeAction


class DurativeValidationError(PlannerError):
    """Raised when a ``DurativeAction`` is structurally invalid."""


def _all_atoms(action: "DurativeAction") -> Iterator[GroundAtom]:
    """Yield every condition and effect atom of the action as a tuple."""
    for time in action.CONDITION_TIMES:
        for atom in action.condition_pos[time]:
            yield atom_tuple(atom)
        for atom in action.condition_neg[time]:
            yield atom_tuple(atom)
    for time in action.EFFECT_TIMES:
        for atom in action.effect_pos[time]:
            yield atom_tuple(atom)
        for atom in action.effect_neg[time]:
            yield atom_tuple(atom)


def validate_durative_action(
    action: "DurativeAction",
    declared_predicates: Optional[Set[str]] = None,
) -> None:
    """Validate a durative action; raise :class:`DurativeValidationError` if
    malformed.

    Checks, in order:

    1. ``duration`` is present and strictly positive.
    2. Every variable (a ``?``-prefixed token) used in a condition/effect is a
       declared parameter of the action (in ``variable_list``).
    3. If ``declared_predicates`` is given, every predicate referenced by a
       condition/effect is declared in the domain.

    ``declared_predicates`` is optional so a single grounded action can be
    validated standalone; pass ``DomainProblem.predicates()`` to enforce check 3.
    """
    name = action.operator_name
    if action.duration is None:
        raise DurativeValidationError(
            "durative action %r has no simple numeric duration" % name
        )
    if action.duration <= 0:
        raise DurativeValidationError(
            "durative action %r has non-positive duration %r" % (name, action.duration)
        )

    params = set(action.variable_list)
    for atom in _all_atoms(action):
        for token in atom:
            if token.startswith("?") and token not in params:
                raise DurativeValidationError(
                    "durative action %r references undeclared parameter %r"
                    % (name, token)
                )
        if declared_predicates is not None and atom and atom[0] not in declared_predicates:
            raise DurativeValidationError(
                "durative action %r references undeclared predicate %r"
                % (name, atom[0])
            )


def validate_durative_actions(domainproblem: "DomainProblem") -> None:
    """Validate every durative action declared in ``domainproblem`` against its
    declared predicates. No-op for domains without durative actions."""
    predicates = domainproblem.predicates()
    for action in domainproblem.domain.durative_operators.values():
        validate_durative_action(action, predicates)


class DurativeState:
    """A small immutable state for checking durative ``at start`` applicability.

    Holds a set of ground atoms (tuples). Unlike :class:`~pddlpy.planning.State`
    it carries no numeric valuation and models no timeline: durative+numeric and
    temporal scheduling are out of scope for 1.0.
    """

    __slots__ = ("_atoms",)

    def __init__(self, atoms: Iterable[Any] = ()) -> None:
        self._atoms: frozenset[GroundAtom] = frozenset(atom_tuple(a) for a in atoms)

    @property
    def atoms(self) -> frozenset[GroundAtom]:
        return self._atoms

    @classmethod
    def from_problem(cls, domainproblem: "DomainProblem") -> "DurativeState":
        """Build the initial durative state from a parsed ``DomainProblem``."""
        return cls(domainproblem.initialstate())

    def applicable(self, action: "DurativeAction") -> bool:
        """True if the grounded ``action`` can *start* in this state.

        Checks only the ``at start`` conditions (positive atoms hold, negative
        atoms do not). ``over all`` / ``at end`` conditions are not evaluated —
        that needs a timeline this type intentionally does not model.
        """
        pos = {atom_tuple(a) for a in action.condition_pos["start"]}
        neg = {atom_tuple(a) for a in action.condition_neg["start"]}
        return pos <= self._atoms and neg.isdisjoint(self._atoms)

    def __contains__(self, atom: Any) -> bool:
        return atom_tuple(atom) in self._atoms

    def __iter__(self) -> Iterator[GroundAtom]:
        return iter(self._atoms)

    def __len__(self) -> int:
        return len(self._atoms)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DurativeState) and self._atoms == other._atoms

    def __hash__(self) -> int:
        return hash(self._atoms)

    def __repr__(self) -> str:
        return "DurativeState(%s)" % sorted(self._atoms)
