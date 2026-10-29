"""Immutable, hashable planning state and plan types.

This is the clean resolution to #21: the parser exposes ground atoms as
``Atom`` objects (``initialstate()`` / ``goals()``) and as plain tuples
(grounded ``Operator`` precondition/effect sets). ``State`` normalizes both
to tuples so that applicability and goal checks work without manual casting.
"""
from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

from pddlpy.pddl import ieee_div

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, DurativeAction, Operator

    #: Any grounded action a plan step can carry — instantaneous or durative
    #: (#84); both expose ``operator_name`` and ``variable_list``.
    PlanAction = Union[Operator, DurativeAction]

#: A ground atom, e.g. ``("on", "a", "b")``.
GroundAtom = Tuple[str, ...]
#: A numeric fluent valuation: ground function head -> value.
Valuation = Dict[GroundAtom, float]


def atom_tuple(atom: Any) -> GroundAtom:
    """Normalize a ground atom to a plain tuple of strings.

    Accepts either a tuple (already normalized, e.g. from a grounded
    ``Operator``) or an ``Atom`` instance (from ``initialstate()`` /
    ``goals()``), which carries a ``predicate`` sequence.
    """
    if isinstance(atom, tuple):
        return atom
    predicate = getattr(atom, "predicate", None)
    if predicate is not None:
        return tuple(predicate)
    return tuple(atom)


def apply_numeric(fluents: Mapping[GroundAtom, float],
                  updates: Iterable[Tuple[GroundAtom, str, float]]) -> Valuation:
    """The valuation after simultaneous numeric effects, each given as
    ``(fluent, op, value)`` with ``value`` already evaluated in ``fluents``.

    ``increase`` / ``decrease`` accumulate: two increases of a fluent by 1
    and 2 add 3, as in VAL. ``assign`` / ``scale-up`` / ``scale-down`` set the
    fluent from its pre-state value; additive updates then apply on top.
    """
    out = dict(fluents)
    delta: Dict[GroundAtom, float] = {}
    for key, op, value in updates:
        if op == "increase":
            delta[key] = delta.get(key, 0.0) + value
        elif op == "decrease":
            delta[key] = delta.get(key, 0.0) - value
        elif op == "assign":
            out[key] = value
        elif op == "scale-up":
            out[key] = fluents.get(key, 0.0) * value
        else:  # scale-down; the grammar allows no other assignOp
            out[key] = ieee_div(fluents.get(key, 0.0), value)
    for key, d in delta.items():
        out[key] = out.get(key, 0.0) + d
    return out


class State:
    """An immutable, hashable planning state.

    Holds a set of ground atoms (tuples of strings, e.g. ``("on", "a", "b")``)
    and, for numeric domains (#11), a valuation mapping ground function heads
    to numbers, e.g. ``{("fuel", "truck"): 100.0}``. Suitable as a key in
    search open/closed sets.
    """

    __slots__ = ("_atoms", "_fluents", "_key")

    def __init__(
        self,
        atoms: Iterable[Any] = (),
        fluents: Optional[Mapping[GroundAtom, float]] = None,
    ) -> None:
        self._atoms: frozenset[GroundAtom] = frozenset(atom_tuple(a) for a in atoms)
        self._fluents: Valuation = dict(fluents or {})
        self._key: Tuple[frozenset[GroundAtom], frozenset] = (
            self._atoms,
            frozenset(self._fluents.items()),
        )

    @property
    def atoms(self) -> frozenset[GroundAtom]:
        return self._atoms

    @property
    def fluents(self) -> Valuation:
        return self._fluents

    # -- constructors -----------------------------------------------------
    @classmethod
    def from_problem(cls, domainproblem: "DomainProblem") -> "State":
        """Build the initial state (atoms + numeric fluents) from a parsed
        ``DomainProblem``."""
        return cls(domainproblem.initialstate(), domainproblem.initial_numeric())

    # -- planning operations (resolve #21) -------------------------------
    def applicable(self, operator: "Operator") -> bool:
        """True if a grounded ``operator`` is applicable in this state.

        When the operator carries a grounded ADL precondition tree (#10) it is
        the authoritative test: the full and/or/not/imply/=/forall/exists
        structure — and any numeric comparison — is evaluated against this
        state. Operators built without a tree fall back to the legacy STRIPS
        conjunctive check (all positive preconditions hold, no negative one
        holds, every numeric precondition satisfied).
        """
        precondition = getattr(operator, "precondition", None)
        if precondition is not None:
            return bool(precondition.holds(self._atoms, self._fluents))
        pos = {atom_tuple(a) for a in operator.precondition_pos}
        neg = {atom_tuple(a) for a in operator.precondition_neg}
        if not (pos <= self._atoms and neg.isdisjoint(self._atoms)):
            return False
        return all(c.holds(self._fluents) for c in operator.precondition_num)

    def apply(self, operator: "Operator") -> "State":
        """Return the successor ``State`` after applying a grounded operator.

        Delete effects are removed first, then add effects are added
        (add-after-delete), matching STRIPS semantics. Numeric effects are
        evaluated against the pre-state valuation (simultaneous semantics).
        """
        add = {atom_tuple(a) for a in operator.effect_pos}
        delete = {atom_tuple(a) for a in operator.effect_neg}
        num_effects = list(operator.effect_num)
        # ADL conditional effects (#10): a (when C E) / universal effect fires
        # only if its guard C holds in the pre-state (simultaneous semantics).
        for ce in getattr(operator, "conditional_effects", ()):
            if ce.condition.holds(self._atoms, self._fluents):
                add |= {atom_tuple(a) for a in ce.add}
                delete |= {atom_tuple(a) for a in ce.dele}
                num_effects.extend(ce.num)
        fluents: Valuation = self._fluents
        if num_effects:
            fluents = apply_numeric(self._fluents, [
                (eff.head.head, eff.op, eff.expr.value(self._fluents)) for eff in num_effects])
        return State((self._atoms - delete) | add, fluents)

    def satisfies(self, goals: Iterable[Any]) -> bool:
        """True if every (positive) goal atom holds in this state."""
        return {atom_tuple(a) for a in goals} <= self._atoms

    # -- container protocol ----------------------------------------------
    def __contains__(self, atom: Any) -> bool:
        return atom_tuple(atom) in self._atoms

    def __iter__(self) -> Iterator[GroundAtom]:
        return iter(self._atoms)

    def __len__(self) -> int:
        return len(self._atoms)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, State) and self._key == other._key

    def __hash__(self) -> int:
        return hash(self._key)

    def __repr__(self) -> str:
        if self._fluents:
            return "State(%s, %s)" % (sorted(self._atoms), dict(sorted(self._fluents.items())))
        return "State(%s)" % sorted(self._atoms)


class Plan:
    """An ordered sequence of grounded actions that reaches a goal.

    ``actions`` is a tuple of grounded ``Operator`` (or, for temporal plans,
    ``DurativeAction``) instances. ``cost`` is the plan cost (defaults to the
    number of actions; action-cost domains override this in a later phase).
    """

    __slots__ = ("actions", "cost")

    def __init__(
        self,
        actions: Iterable["PlanAction"] = (),
        cost: Optional[float] = None,
    ) -> None:
        self.actions: Tuple["PlanAction", ...] = tuple(actions)
        self.cost: float = len(self.actions) if cost is None else cost

    def __iter__(self) -> Iterator["PlanAction"]:
        return iter(self.actions)

    def __len__(self) -> int:
        return len(self.actions)

    def action_names(self) -> List[Tuple[Optional[str], Dict[str, Optional[str]]]]:
        """List of ``(operator_name, variable_bindings)`` for each action."""
        return [(a.operator_name, a.variable_list) for a in self.actions]

    def __repr__(self) -> str:
        steps = ", ".join(
            "%s(%s)" % (a.operator_name, ", ".join(str(v) for v in a.variable_list.values()))
            for a in self.actions
        )
        return "Plan[cost=%s]: %s" % (self.cost, steps)
