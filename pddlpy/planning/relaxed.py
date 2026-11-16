"""Relaxed exploration: what the task can reach if nothing is ever deleted.

The delete relaxation over a ``GroundedTask``. Only the atoms a condition
needs in every case count as its relaxed precondition: the positive literals
of its top-level conjunction. Negative literals, disjunctions, existentials,
equality, numeric comparisons and derived atoms (#141) count as satisfiable,
and a conditional effect adds its atoms whether or not its guard holds. The
result over-approximates what is reachable, so an atom or action it calls
unreachable is unreachable in the real task.

``RelaxedTask`` compiles the actions once. ``explore`` then runs the
standard counter-based fixpoint (each action waits for its number of
unreached preconditions), which the hFF heuristic reuses from every state.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, AbstractSet, Dict, FrozenSet, Iterable, List, Set

from pddlpy.pddl import And, Lit

from .state import atom_tuple

if TYPE_CHECKING:
    from pddlpy.pddl import Condition, Operator

    from .grounding import GroundedTask
    from .state import GroundAtom


def needed_atoms(cond: "Condition | None", skip: AbstractSet[str] = frozenset()
                 ) -> Set["GroundAtom"]:
    """The atoms ``cond`` needs in every case: the positive literals of its
    top-level conjunction, nested ``and`` included, except predicates in
    ``skip``. Every other part counts as satisfiable."""
    if isinstance(cond, Lit):
        atom = atom_tuple(cond.atom)
        return set() if atom[0] in skip else {atom}
    if isinstance(cond, And):
        return set().union(*(needed_atoms(c, skip) for c in cond.children))
    return set()


class Exploration:
    """What a relaxed exploration reached.

    Attributes:
        atoms   -- the reachable atoms (the start atoms included).
        actions -- indices into ``GroundedTask.actions`` of the reachable
                   actions, in the order they became applicable.
        goals   -- the goal atoms the goal needs that were not reached.
    """

    __slots__ = ("atoms", "actions", "goals")

    def __init__(self, atoms: FrozenSet["GroundAtom"], actions: List[int],
                 goals: FrozenSet["GroundAtom"]) -> None:
        self.atoms = atoms
        self.actions = actions
        self.goals = goals

    @property
    def solvable(self) -> bool:
        """False if a goal atom is unreachable, which proves the task
        unsolvable; True says only that the relaxation found no proof."""
        return not self.goals


class RelaxedTask:
    """The actions of a ``GroundedTask`` compiled for relaxed exploration.

    Attributes:
        task  -- the ``GroundedTask``.
        pre   -- per action, the atoms it needs (``needed_atoms``).
        add   -- per action, the atoms it adds, conditional adds included.
        goal  -- the atoms the goal needs.
    """

    def __init__(self, task: "GroundedTask") -> None:
        self.task = task
        derived = {rule.predicate for rule in task.domainproblem.domain.derived}
        self.pre: List[FrozenSet["GroundAtom"]] = []
        self.add: List[FrozenSet["GroundAtom"]] = []
        #: atom -> the actions that need it
        self.needed_by: Dict["GroundAtom", List[int]] = {}
        for i, action in enumerate(task.actions):
            pre = frozenset(_precondition(action, derived))
            self.pre.append(pre)
            self.add.append(frozenset(_adds(action)))
            for atom in pre:
                self.needed_by.setdefault(atom, []).append(i)
        self.goal: FrozenSet["GroundAtom"] = frozenset(needed_atoms(task.goal, derived))

    def explore(self, atoms: Iterable["GroundAtom"] | None = None) -> Exploration:
        """Reach a fixpoint from ``atoms`` (default: the initial state)."""
        reached: Set["GroundAtom"] = set(self.task.initial.atoms if atoms is None else atoms)
        waiting = [len(p) for p in self.pre]
        applied = [i for i, n in enumerate(waiting) if n == 0]
        queue = list(reached)
        q = k = 0
        while q < len(queue) or k < len(applied):
            if q < len(queue):  # a new atom: count it off the actions that need it
                for i in self.needed_by.get(queue[q], ()):
                    waiting[i] -= 1
                    if waiting[i] == 0:
                        applied.append(i)
                q += 1
            else:  # a new action: reach what it adds
                for atom in self.add[applied[k]]:
                    if atom not in reached:
                        reached.add(atom)
                        queue.append(atom)
                k += 1
        return Exploration(frozenset(reached), applied, self.goal - reached)


def _precondition(action: "Operator", derived: AbstractSet[str]) -> Set["GroundAtom"]:
    precondition = getattr(action, "precondition", None)
    if precondition is not None:
        return needed_atoms(precondition, derived)
    return {a for a in map(atom_tuple, action.precondition_pos) if a[0] not in derived}


def _adds(action: "Operator") -> Set["GroundAtom"]:
    adds = {atom_tuple(a) for a in action.effect_pos}
    for ce in action.conditional_effects:
        adds |= {atom_tuple(a) for a in ce.add}
    return adds
