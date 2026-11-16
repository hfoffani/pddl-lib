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
unreached preconditions). ``ff`` runs the same fixpoint layer by layer over
integer atom ids, from every search state, and returns the hFF heuristic
(Hoffmann & Nebel 2001): the number of actions in a relaxed plan.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, AbstractSet, Dict, FrozenSet, Iterable, List, Optional, Set

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
        # the same, over integer atom ids, for ``ff``
        self._id: Dict["GroundAtom", int] = {}
        for atoms in (*self.pre, *self.add, self.goal):
            for atom in atoms:
                self._id.setdefault(atom, len(self._id))
        self._pre = [tuple(self._id[a] for a in p) for p in self.pre]
        self._add = [tuple(self._id[a] for a in a_) for a_ in self.add]
        self._needed_by: List[List[int]] = [[] for _ in self._id]
        for i, pre_ids in enumerate(self._pre):
            for a in pre_ids:
                self._needed_by[a].append(i)
        self._npre = [len(p) for p in self._pre]
        self._free = [i for i, n in enumerate(self._npre) if n == 0]
        self._goal = tuple(self._id[a] for a in self.goal)

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

    def ff(self, atoms: Iterable["GroundAtom"]) -> Optional[int]:
        """hFF from the state with these ``atoms``: the size of a relaxed
        plan, or ``None`` if a goal atom is unreachable (a dead end).

        Layer by layer, each newly reached atom records the action that
        first reached it; the relaxed plan collects those supporters
        backwards from the goal atoms. 0 means the goal's needed atoms hold,
        not that the state is a goal."""
        ids = self._id
        level: Dict[int, int] = {}
        for atom in atoms:
            a = ids.get(atom)
            if a is not None:
                level[a] = 0
        supporter: Dict[int, int] = {}
        goal = self._goal
        missing = sum(1 for g in goal if g not in level)
        waiting = self._npre[:]
        needed_by, add = self._needed_by, self._add
        layer = list(level)
        ready = list(self._free)
        depth = 0
        while missing:
            for a in layer:
                for i in needed_by[a]:
                    waiting[i] -= 1
                    if waiting[i] == 0:
                        ready.append(i)
            if not ready:
                return None
            depth += 1
            layer = []
            for i in ready:
                for a in add[i]:
                    if a not in level:
                        level[a] = depth
                        supporter[a] = i
                        layer.append(a)
            ready = []
            missing = sum(1 for g in goal if g not in level)
        plan: Set[int] = set()
        stack = list(goal)
        seen: Set[int] = set()
        pre = self._pre
        while stack:
            a = stack.pop()
            if a in seen or level[a] == 0:
                continue
            seen.add(a)
            i = supporter[a]
            if i not in plan:
                plan.add(i)
                stack.extend(pre[i])
        return len(plan)


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
