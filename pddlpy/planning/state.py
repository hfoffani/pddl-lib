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
    Set,
    Tuple,
    Union,
)

from pddlpy.pddl import (
    And,
    Condition,
    Lit,
    Not,
    NumericCond,
    Or,
    _expr_fluents,
    _rank,
    _reads,
    holds3,
    ieee_div,
    undefined_marker,
)

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
        ``DomainProblem``, derived atoms included (#141)."""
        state = cls(domainproblem.initialstate(), domainproblem.initial_numeric())
        return state.derived(domainproblem)

    def derived(self, domainproblem: "DomainProblem") -> "State":
        """This state with its derived atoms recomputed (#141); itself if the
        domain has no ``(:derived ...)`` rules."""
        if not domainproblem.domain.derived:
            return self
        return State(domainproblem.derive(self._atoms, self._fluents), self._fluents)

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

    def __bool__(self) -> bool:
        """Always true: a Plan is a solution, even the empty one.

        Planners return ``None`` when there is no solution, so ``if plan:``
        must not treat the zero-step plan for an already-satisfied goal as
        a failure.
        """
        return True

    def action_names(self) -> List[Tuple[Optional[str], Dict[str, Optional[str]]]]:
        """List of ``(operator_name, variable_bindings)`` for each action."""
        return [(a.operator_name, a.variable_list) for a in self.actions]

    def __repr__(self) -> str:
        steps = ", ".join(
            "%s(%s)" % (a.operator_name, ", ".join(str(v) for v in a.variable_list.values()))
            for a in self.actions
        )
        return "Plan[cost=%s]: %s" % (self.cost, steps)


# -- fluents a condition reads, in VAL's order (#166, #138) -----------------

def _evaluated_fluents(c: Optional[Condition], state: State) -> Set[GroundAtom]:
    """The fluents evaluating ``c`` in ``state`` reads, in VAL's order
    (``ConjGoal`` / ``DisjGoal::evaluate``): ``and`` evaluates its children
    cheapest first (atoms before comparisons, a stable sort by
    :func:`_rank`), ``or`` in written order, and both stop once the result
    is known. A fluent behind a false conjunct or a true disjunct is never
    read. A derived atom marked undefined (#141) counts as a read with no
    value too."""
    if isinstance(c, Lit):
        atom = tuple(c.atom.predicate)
        return {atom} if undefined_marker(atom) in state.atoms else set()
    if isinstance(c, NumericCond):
        return set(_expr_fluents(c.constraint.lhs)) | set(_expr_fluents(c.constraint.rhs))
    if isinstance(c, Not):
        return _evaluated_fluents(c.child, state)
    if isinstance(c, (And, Or)):
        out: Set[GroundAtom] = set()
        children = sorted(c.children, key=_rank) if isinstance(c, And) else c.children
        for child in children:
            out |= _evaluated_fluents(child, state)
            if child.holds(state.atoms, state.fluents) is not isinstance(c, And):
                break  # a false conjunct / true disjunct settles it
        return out
    return set()  # Equality, or no condition


def goal_holds(goal: Condition, state: State) -> bool:
    """True if ``goal`` holds in ``state`` and evaluating it reads no fluent
    without a value nor an undefined derived atom: VAL fails such a read
    instead of reading 0 or false (#141)."""
    return holds3(goal, state.atoms, state.fluents) is True


def preference_undefined(pref: Condition, state: State) -> Set[GroundAtom]:
    """The fluents with no value and the undefined derived atoms that judging
    a preference instance at the end of a plan reads (#201). A satisfied one
    reads what :func:`goal_holds` does; for a violated one VAL also collects
    advice (``getAdviceProp``), which evaluates every part, so every read
    counts."""
    if goal_holds(pref, state):
        return set()
    atoms, fluents = _reads(pref)
    return ({f for f in fluents if f not in state.fluents}
            | {a for a in atoms if undefined_marker(a) in state.atoms})
