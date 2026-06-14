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
    """An immutable, hashable set of ground atoms.

    Atoms are stored as tuples of strings, e.g. ``("on", "a", "b")``.
    Suitable as a key in search open/closed sets.
    """

    __slots__ = ("_atoms",)

    def __init__(self, atoms=()):
        self._atoms = frozenset(atom_tuple(a) for a in atoms)

    @property
    def atoms(self):
        return self._atoms

    # -- constructors -----------------------------------------------------
    @classmethod
    def from_problem(cls, domainproblem):
        """Build the initial state from a parsed ``DomainProblem``."""
        return cls(domainproblem.initialstate())

    # -- planning operations (resolve #21) -------------------------------
    def applicable(self, operator):
        """True if a grounded ``operator`` is applicable in this state.

        Conjunctive semantics: all positive preconditions hold and no
        negative precondition holds. Disjunctive preconditions
        (``precondition_connective == 'or'``) are not modeled here; the
        reference planners gate such domains via capability negotiation.
        """
        pos = {atom_tuple(a) for a in operator.precondition_pos}
        neg = {atom_tuple(a) for a in operator.precondition_neg}
        return pos <= self._atoms and neg.isdisjoint(self._atoms)

    def apply(self, operator):
        """Return the successor ``State`` after applying a grounded operator.

        Delete effects are removed first, then add effects are added
        (add-after-delete), matching STRIPS semantics.
        """
        add = {atom_tuple(a) for a in operator.effect_pos}
        delete = {atom_tuple(a) for a in operator.effect_neg}
        return State((self._atoms - delete) | add)

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
        return isinstance(other, State) and self._atoms == other._atoms

    def __hash__(self):
        return hash(self._atoms)

    def __repr__(self):
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
