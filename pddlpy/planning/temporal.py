"""Sequential temporal planner over durative actions (#84).

Solves durative-action domains by compressing each grounded
``DurativeAction`` into an atomic transition. Under **sequential semantics**
actions never overlap, so the state is constant while an action executes:

1. the ``at start`` conditions must hold in the current state;
2. start effects are applied at the start time point;
3. the ``over all`` invariant and the ``at end`` conditions are checked
   against the mid-state (after the start effects) — the state that persists
   through the open interval and at the end point;
4. end effects are applied at ``start + duration``.

An action whose own start effects violate its ``over all`` / ``at end``
conditions is therefore never executable — the constraint an
``at start``-only check (:class:`~pddlpy.planning.DurativeState`) cannot
express. Instantaneous actions participate as zero-duration steps, so mixed
domains work.

``TemporalPlanner`` (registered as ``"temporal"``) runs uniform-cost search
over accumulated duration and returns a :class:`TemporalPlan` carrying
per-step start times, durations and a ``makespan`` (= ``cost``), minimal for
sequential schedules. *Required concurrency* (actions that must overlap, e.g.
matchcellar) is out of scope — a follow-up to this planner.
"""
from __future__ import annotations

import heapq
import itertools
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Optional,
    Tuple,
)

from .base import Planner, validate_requirements
from .durative import validate_durative_actions
from .registry import register
from .search import STRIPS_CAPABILITIES
from .state import Plan, State, atom_tuple

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, DurativeAction, Operator

    from .state import PlanAction

#: Parent-pointer map used to reconstruct a schedule.
_CameFrom = Dict[State, Tuple[State, "PlanAction", float]]

#: Requirements the temporal planner supports: the STRIPS set plus
#: :durative-actions.
TEMPORAL_CAPABILITIES: FrozenSet[str] = STRIPS_CAPABILITIES | {":durative-actions"}


class ScheduledAction:
    """One step of a temporal plan: a grounded action, its start time and
    its duration (``end == start + duration``; 0 for instantaneous steps)."""

    __slots__ = ("action", "start", "duration")

    def __init__(self, action: "PlanAction", start: float, duration: float) -> None:
        self.action = action
        self.start = start
        self.duration = duration

    @property
    def end(self) -> float:
        return self.start + self.duration

    def __repr__(self) -> str:
        return "%g: %s(%s) [%g]" % (
            self.start,
            self.action.operator_name,
            ", ".join(str(v) for v in self.action.variable_list.values()),
            self.duration,
        )


class TemporalPlan(Plan):
    """A :class:`Plan` whose steps carry start times and durations (#84).

    ``steps`` is a tuple of :class:`ScheduledAction`; ``actions`` /
    ``action_names()`` keep the base ``Plan`` contract. ``makespan`` is the
    end time of the schedule and doubles as the plan ``cost``.
    """

    __slots__ = ("steps", "makespan")

    def __init__(self, steps: Iterable[ScheduledAction] = ()) -> None:
        self.steps: Tuple[ScheduledAction, ...] = tuple(steps)
        self.makespan: float = max((s.end for s in self.steps), default=0.0)
        super().__init__((s.action for s in self.steps), cost=self.makespan)

    def __repr__(self) -> str:
        return "TemporalPlan[makespan=%g]: %s" % (
            self.makespan,
            ", ".join(repr(s) for s in self.steps),
        )


def _holds(state: State, pos: Iterable[Any], neg: Iterable[Any]) -> bool:
    """Conjunctive check: every atom in ``pos`` holds, none in ``neg`` does."""
    return {atom_tuple(a) for a in pos} <= state.atoms and {
        atom_tuple(a) for a in neg
    }.isdisjoint(state.atoms)


def _apply_effects(state: State, add: Iterable[Any], delete: Iterable[Any]) -> State:
    """Add-after-delete effect application, preserving the numeric valuation."""
    return State(
        (state.atoms - {atom_tuple(a) for a in delete})
        | {atom_tuple(a) for a in add},
        state.fluents,
    )


def apply_durative(state: State, action: "DurativeAction") -> Optional[State]:
    """Apply a grounded durative action under sequential semantics.

    Returns the successor ``State``, or ``None`` when the action cannot run:
    the ``at start`` conditions fail in ``state``, or the ``over all``
    invariant / ``at end`` conditions fail in the mid-state (after the start
    effects — with no concurrent activity, that state holds for the whole
    duration and at the end point).
    """
    if not _holds(state, action.condition_pos["start"], action.condition_neg["start"]):
        return None
    mid = _apply_effects(state, action.effect_pos["start"], action.effect_neg["start"])
    if not _holds(mid, action.condition_pos["over"], action.condition_neg["over"]):
        return None
    if not _holds(mid, action.condition_pos["end"], action.condition_neg["end"]):
        return None
    return _apply_effects(mid, action.effect_pos["end"], action.effect_neg["end"])


class TemporalTask:
    """The temporal counterpart of ``GroundedTask``: initial state, goals and
    every grounded action — durative, plus instantaneous ones as zero-duration
    steps (so mixed domains work)."""

    def __init__(self, domainproblem: "DomainProblem") -> None:
        self.domainproblem = domainproblem
        self.initial: State = State.from_problem(domainproblem)
        self.goals = domainproblem.goals()
        self.durative: List["DurativeAction"] = [
            g
            for name in domainproblem.durative_operators()
            for g in domainproblem.ground_durative_operator(name)
        ]
        self.instantaneous: List["Operator"] = [
            g
            for name in domainproblem.operators()
            for g in domainproblem.ground_operator(name)
        ]

    def successors(self, state: State) -> Iterator[Tuple["PlanAction", float, State]]:
        """Yield ``(action, duration, successor)`` for every executable action."""
        for op in self.instantaneous:
            if state.applicable(op):
                yield op, 0.0, state.apply(op)
        for da in self.durative:
            succ = apply_durative(state, da)
            if succ is not None:
                yield da, float(da.duration or 0.0), succ

    def is_goal(self, state: State) -> bool:
        """True if ``state`` satisfies the goal."""
        return state.satisfies(self.goals)


def _schedule(came_from: _CameFrom, state: State) -> TemporalPlan:
    """Walk parent pointers back to the start, then lay the actions end to
    end — sequential semantics: each starts when the previous one finishes."""
    pairs: List[Tuple["PlanAction", float]] = []
    while state in came_from:
        prev, action, duration = came_from[state]
        pairs.append((action, duration))
        state = prev
    pairs.reverse()
    steps: List[ScheduledAction] = []
    clock = 0.0
    for action, duration in pairs:
        steps.append(ScheduledAction(action, clock, duration))
        clock += duration
    return TemporalPlan(steps)


class TemporalPlanner(Planner):
    """Uniform-cost search over accumulated duration (Dijkstra): returns a
    makespan-minimal *sequential* schedule as a :class:`TemporalPlan`, or
    ``None``. Durative actions are validated (#23) before search so malformed
    durations fail fast."""

    capabilities = TEMPORAL_CAPABILITIES

    def solve(self, domainproblem: "DomainProblem") -> Optional[TemporalPlan]:
        validate_requirements(domainproblem)
        self.check_capabilities(domainproblem)
        validate_durative_actions(domainproblem)
        task = TemporalTask(domainproblem)
        start = task.initial
        counter = itertools.count()  # tie-breaker; keeps States out of compares
        frontier: List[Tuple[float, int, State]] = [(0.0, next(counter), start)]
        best_g: Dict[State, float] = {start: 0.0}
        came_from: _CameFrom = {}
        while frontier:
            g, _, state = heapq.heappop(frontier)
            if task.is_goal(state):
                return _schedule(came_from, state)
            if g > best_g.get(state, g):
                continue  # pragma: no cover - stale heap entry (lazy deletion)
            for action, duration, succ in task.successors(state):
                ng = g + duration
                if ng < best_g.get(succ, ng + 1.0):
                    best_g[succ] = ng
                    came_from[succ] = (state, action, duration)
                    heapq.heappush(frontier, (ng, next(counter), succ))
        return None


register("temporal", TemporalPlanner)
