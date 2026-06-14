"""Immutable, hashable planning state and plan types.

This is the clean resolution to #21: the parser exposes ground atoms as
``Atom`` objects (``initialstate()`` / ``goals()``) and as plain tuples
(grounded ``Operator`` precondition/effect sets). ``State`` normalizes both
to tuples so that applicability and goal checks work without manual casting.
"""


def atom_tuple(atom):
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


class State:
    """An immutable, hashable planning state.

    Holds a set of ground atoms (tuples of strings, e.g. ``("on", "a", "b")``)
    and, for numeric domains (#11), a valuation mapping ground function heads
    to numbers, e.g. ``{("fuel", "truck"): 100.0}``. Suitable as a key in
    search open/closed sets.
    """

    __slots__ = ("_atoms", "_fluents", "_key")

    def __init__(self, atoms=(), fluents=None):
        self._atoms = frozenset(atom_tuple(a) for a in atoms)
        self._fluents = dict(fluents or {})
        self._key = (self._atoms, frozenset(self._fluents.items()))

    @property
    def atoms(self):
        return self._atoms

    @property
    def fluents(self):
        return self._fluents

    # -- constructors -----------------------------------------------------
    @classmethod
    def from_problem(cls, domainproblem):
        """Build the initial state (atoms + numeric fluents) from a parsed
        ``DomainProblem``."""
        return cls(domainproblem.initialstate(), domainproblem.initial_numeric())

    # -- planning operations (resolve #21) -------------------------------
    def applicable(self, operator):
        """True if a grounded ``operator`` is applicable in this state.

        Conjunctive semantics: all positive preconditions hold, no negative
        precondition holds, and every numeric precondition is satisfied under
        the current fluent valuation. Disjunctive preconditions
        (``precondition_connective == 'or'``) are not modeled here; the
        reference planners gate such domains via capability negotiation.
        """
        pos = {atom_tuple(a) for a in operator.precondition_pos}
        neg = {atom_tuple(a) for a in operator.precondition_neg}
        if not (pos <= self._atoms and neg.isdisjoint(self._atoms)):
            return False
        return all(c.holds(self._fluents) for c in operator.precondition_num)

    def apply(self, operator):
        """Return the successor ``State`` after applying a grounded operator.

        Delete effects are removed first, then add effects are added
        (add-after-delete), matching STRIPS semantics. Numeric effects are
        evaluated against the pre-state valuation (simultaneous semantics).
        """
        add = {atom_tuple(a) for a in operator.effect_pos}
        delete = {atom_tuple(a) for a in operator.effect_neg}
        fluents = self._fluents
        if operator.effect_num:
            updates = [eff.apply(self._fluents) for eff in operator.effect_num]
            fluents = dict(self._fluents)
            for key, value in updates:
                fluents[key] = value
        return State((self._atoms - delete) | add, fluents)

    def satisfies(self, goals):
        """True if every (positive) goal atom holds in this state."""
        return {atom_tuple(a) for a in goals} <= self._atoms

    # -- container protocol ----------------------------------------------
    def __contains__(self, atom):
        return atom_tuple(atom) in self._atoms

    def __iter__(self):
        return iter(self._atoms)

    def __len__(self):
        return len(self._atoms)

    def __eq__(self, other):
        return isinstance(other, State) and self._key == other._key

    def __hash__(self):
        return hash(self._key)

    def __repr__(self):
        if self._fluents:
            return "State(%s, %s)" % (sorted(self._atoms), dict(sorted(self._fluents.items())))
        return "State(%s)" % sorted(self._atoms)


class Plan:
    """An ordered sequence of grounded actions that reaches a goal.

    ``actions`` is a tuple of grounded ``Operator`` instances. ``cost`` is
    the plan cost (defaults to the number of actions; action-cost domains
    override this in a later phase).
    """

    __slots__ = ("actions", "cost")

    def __init__(self, actions=(), cost=None):
        self.actions = tuple(actions)
        self.cost = len(self.actions) if cost is None else cost

    def __iter__(self):
        return iter(self.actions)

    def __len__(self):
        return len(self.actions)

    def action_names(self):
        """List of ``(operator_name, variable_bindings)`` for each action."""
        return [(a.operator_name, a.variable_list) for a in self.actions]

    def __repr__(self):
        steps = ", ".join(
            "%s(%s)" % (a.operator_name, ", ".join(str(v) for v in a.variable_list.values()))
            for a in self.actions
        )
        return "Plan[cost=%s]: %s" % (self.cost, steps)
