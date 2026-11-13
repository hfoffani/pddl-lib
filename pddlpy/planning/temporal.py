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
sequential schedules whose steps are ``SEPARATION`` apart (#165): the search
charges each step its duration plus that gap. *Required concurrency* (actions that must overlap, e.g.
matchcellar) is out of scope — a follow-up to this planner.
"""
from __future__ import annotations

import bisect
import heapq
import itertools
import math
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
)

from .base import Planner, UnsupportedRequirementsError, check_modeled, validate_requirements
from .durative import validate_durative_actions
from .registry import register
from .search import STRIPS_CAPABILITIES
from .state import GroundAtom, Plan, State, atom_tuple, goal_holds

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, DurativeAction, Operator

    from .state import PlanAction

#: A search node: the state and how many timed-literal groups have fired.
_Node = Tuple[State, int]

#: Parent-pointer map used to reconstruct a schedule: the previous node and
#: the step taken (``None`` for a wait), its start time and its duration.
_CameFrom = Dict[_Node, Tuple[_Node, Optional["PlanAction"], float, float]]

#: Time between the end of one scheduled step and the start of the next
#: (#165). Plan validators (VAL) treat happenings within 0.001 of each other
#: as simultaneous and reject them when one depends on the other; 0.01 is
#: VAL's default tolerance, as used by POPF/OPTIC.
SEPARATION = 0.01

#: VAL's tolerance: happenings closer than this are simultaneous. A step
#: never starts or ends this close to a timed initial literal (#142).
TOLERANCE = 0.001


def planned_duration(da: "DurativeAction") -> float:
    """The duration temporal gives ``da`` (#143): the lower bound once it
    is more than ``TOLERANCE`` (start and end are then separate
    happenings), else twice ``TOLERANCE``; never past the upper bound."""
    lo, hi = da.bounds() or (0.0, 0.0)
    return min(lo if lo > TOLERANCE else 2 * TOLERANCE, hi)

#: Requirements the temporal planner supports: the STRIPS set plus
#: :durative-actions and :timed-initial-literals.
TEMPORAL_CAPABILITIES: FrozenSet[str] = STRIPS_CAPABILITIES | {
    ":durative-actions", ":duration-inequalities", ":timed-initial-literals"}


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


def apply_durative(state: State, action: "DurativeAction",
                   during: Iterable[Tuple[Iterable[Any], Iterable[Any]]] = ()) -> Optional[State]:
    """Apply a grounded durative action under sequential semantics.

    Returns the successor ``State``, or ``None`` when the action cannot run:
    the ``at start`` conditions fail in ``state``, or the ``over all``
    invariant / ``at end`` conditions fail in the mid-state (after the start
    effects — with no concurrent activity, that state holds for the whole
    duration and at the end point). ``during`` lists the ``(adds, deletes)``
    of the timed initial literals that happen while it runs (#142): each
    changes the mid-state, and the invariant must hold after each.
    """
    if not _holds(state, action.condition_pos["start"], action.condition_neg["start"]):
        return None
    mid = _apply_effects(state, action.effect_pos["start"], action.effect_neg["start"])
    if not _holds(mid, action.condition_pos["over"], action.condition_neg["over"]):
        return None
    for adds, dels in during:
        mid = _apply_effects(mid, adds, dels)
        if not _holds(mid, action.condition_pos["over"], action.condition_neg["over"]):
            return None
    if not _holds(mid, action.condition_pos["end"], action.condition_neg["end"]):
        return None
    return _apply_effects(mid, action.effect_pos["end"], action.effect_neg["end"])


def contradictory_literals(timed_literals: Iterable[Tuple[float, Any, bool]]
                           ) -> List[Tuple[float, GroundAtom]]:
    """``(time, atom)`` for each atom that timed initial literals add and
    delete in one happening (#142): within ``TOLERANCE`` of the happening's
    first time, as plan validation groups them. VAL rejects every plan."""
    ordered = sorted((t, atom_tuple(a), pos) for t, a, pos in timed_literals)
    out: List[Tuple[float, GroundAtom]] = []
    i = 0
    while i < len(ordered):
        t0 = ordered[i][0]
        j = i
        while j < len(ordered) and ordered[j][0] <= t0 + TOLERANCE:
            j += 1
        adds = {a for _, a, pos in ordered[i:j] if pos}
        dels = {a for _, a, pos in ordered[i:j] if not pos}
        out += [(t0, a) for a in sorted(adds & dels)]
        i = j
    return out


class TemporalTask:
    """The temporal counterpart of ``GroundedTask``: initial state, goals and
    every grounded action — durative, plus instantaneous ones as zero-duration
    steps (so mixed domains work)."""

    def __init__(self, domainproblem: "DomainProblem") -> None:
        self.domainproblem = domainproblem
        self.goals = domainproblem.goals()
        self.goal = domainproblem.goal_condition()
        # Timed initial literals (#142), grouped by time: (time, adds, dels).
        groups: Dict[float, Tuple[set, set]] = {}
        for time, atom, positive in domainproblem.problem.timed_literals:
            adds, dels = groups.setdefault(time, (set(), set()))
            (adds if positive else dels).add(atom_tuple(atom))
        self.tils: List[Tuple[float, set, set]] = [
            (t, a, d) for t, (a, d) in sorted(groups.items())]
        self.til_times: List[float] = [t for t, _, _ in self.tils]
        # literals that add and delete one atom at the same time are mutex,
        # as in VAL: no plan is valid
        self.contradictory = bool(contradictory_literals(domainproblem.problem.timed_literals))
        self.initial_clock = self.clear(0.0)
        self.initial: State
        self.initial, self.initial_fired = self.fire(
            State.from_problem(domainproblem), 0, self.initial_clock)
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
        """Yield ``(action, duration, successor)`` for every action executable
        in ``state``, ignoring timed initial literals (see
        :meth:`timed_successors`)."""
        for op in self.instantaneous:
            if state.applicable(op):
                yield op, 0.0, state.apply(op)
        for da in self.durative:
            succ = apply_durative(state, da)
            if succ is not None:
                yield da, planned_duration(da), succ

    def is_goal(self, state: State) -> bool:
        """True if ``state`` satisfies the goal."""
        return goal_holds(self.goal, state)

    def fire(self, state: State, fired: int, clock: float) -> Tuple[State, int]:
        """Apply the timed-literal groups from ``fired`` on whose time is at
        or before ``clock``; return the state and the new count."""
        while fired < len(self.tils) and self.tils[fired][0] <= clock:
            _, adds, dels = self.tils[fired]
            state = State((state.atoms - dels) | adds, state.fluents)
            fired += 1
        return state, fired

    def near_til(self, time: float) -> bool:
        """True if a timed literal happens within ``TOLERANCE`` of ``time``."""
        i = bisect.bisect_left(self.til_times, time - TOLERANCE)
        return i < len(self.til_times) and self.til_times[i] <= time + TOLERANCE

    def clear(self, time: float) -> float:
        """The first time from ``time`` on, in ``SEPARATION`` steps, that is
        not within ``TOLERANCE`` of a timed literal: when a step can start."""
        while self.near_til(time):
            time += SEPARATION
        return time

    def timed_successors(self, state: State, fired: int, clock: float
                         ) -> Iterator[Tuple[Optional["PlanAction"], float, float,
                                             State, int, float]]:
        """Yield ``(step, start, duration, successor, fired, next_clock)``
        from a node at ``clock`` (never within ``TOLERANCE`` of a timed
        literal): every step that can start then; a wait (step ``None``)
        until just after the next timed literal; and each durative action
        delayed so it ends just after a later literal, for an ``at end``
        window that opens then (the delay and the action are one successor,
        so the later node is not taken for the earlier one), or, with a
        duration range, stretched from now to end just after one (#143). A step does not
        end within ``TOLERANCE`` of a timed literal either (#142)."""
        if fired < len(self.tils):
            wake = self.clear(self.tils[fired][0] + SEPARATION)
            succ, nfired = self.fire(state, fired, wake)
            yield None, clock, wake - clock, succ, nfired, wake
        for op in self.instantaneous:
            if state.applicable(op):
                after = self.clear(clock + SEPARATION)
                succ, nfired = self.fire(state.apply(op), fired, after)
                yield op, clock, 0.0, succ, nfired, after
        for da in self.durative:
            shortest = planned_duration(da)
            _, hi = da.bounds() or (0.0, 0.0)
            candidates: Set[Tuple[float, float]] = set()
            # the shortest and the longest duration, each started now or
            # delayed so the action ends just after a later literal, for an
            # ``at end`` window that opens then
            for duration in {shortest, hi} - {math.inf}:
                candidates.add((clock, duration))
                candidates.update(
                    (self.clear(t + SEPARATION - duration), duration)
                    for t in self.til_times[fired:] if t + SEPARATION - duration > clock)
            # a duration range can also stretch the action from now so it
            # ends just after a later literal (#143)
            candidates.update(
                (clock, self.clear(t + SEPARATION) - clock) for t in self.til_times[fired:]
                if shortest < self.clear(t + SEPARATION) - clock <= hi)
            for start, duration in sorted(candidates):
                end = start + duration
                if self.near_til(end):
                    continue
                before, nfired = self.fire(state, fired, start)
                # the timed literals strictly inside [start, end]
                inside = bisect.bisect_left(self.til_times, end, lo=nfired)
                ran = apply_durative(before, da,
                                     [(a, d) for _, a, d in self.tils[nfired:inside]])
                if ran is not None:
                    after = self.clear(end + SEPARATION)
                    succ, nfired_after = self.fire(ran, inside, after)
                    yield da, start, duration, succ, nfired_after, after


def _schedule(came_from: _CameFrom, node: _Node) -> TemporalPlan:
    """Walk parent pointers back to the start. Under sequential semantics
    each step starts ``SEPARATION`` after the previous one finishes, or
    after the timed literal it waited for."""
    steps: List[ScheduledAction] = []
    while node in came_from:
        node, action, start, duration = came_from[node]
        if action is not None:
            steps.append(ScheduledAction(action, start, duration))
    steps.reverse()
    return TemporalPlan(steps)


def _refuse_unmodeled(domainproblem: "DomainProblem") -> None:
    """Refuse durative actions with parts the model drops (numeric,
    conditional, quantified): searching without them returns wrong plans
    (#139)."""
    if domainproblem.domain.derived:
        raise UnsupportedRequirementsError(
            "temporal planner does not support derived predicates, (:derived "
            "...); the classical planners do (#141)")
    for name, action in sorted(domainproblem.domain.durative_operators.items()):
        if not action.simple:
            raise UnsupportedRequirementsError(
                "temporal planner supports only durative actions with literal "
                "conditions and effects; %s has numeric, conditional or "
                "quantified parts (#139)" % name)


class TemporalPlanner(Planner):
    """Uniform-cost search over accumulated duration (Dijkstra): returns a
    makespan-minimal *sequential* schedule as a :class:`TemporalPlan`, or
    ``None``. Durative actions are validated (#23) before search so malformed
    durations fail fast."""

    capabilities = TEMPORAL_CAPABILITIES

    def solve(self, domainproblem: "DomainProblem") -> Optional[TemporalPlan]:
        validate_requirements(domainproblem)
        check_modeled(domainproblem, timed=True)
        self.check_capabilities(domainproblem)
        validate_durative_actions(domainproblem)
        _refuse_unmodeled(domainproblem)
        task = TemporalTask(domainproblem)
        if task.contradictory:
            return None
        self._start_search()
        start: _Node = (task.initial, task.initial_fired)
        counter = itertools.count()  # tie-breaker; keeps States out of compares
        # g is the clock: when the next step can start
        g0 = task.initial_clock
        frontier: List[Tuple[float, int, _Node]] = [(g0, next(counter), start)]
        best_g: Dict[_Node, float] = {start: g0}
        came_from: _CameFrom = {}
        while frontier:
            g, _, node = heapq.heappop(frontier)
            state, fired = node
            # the goal is judged after every timed literal, as in VAL (#142)
            if task.is_goal(task.fire(state, fired, float("inf"))[0]):
                return _schedule(came_from, node)
            if g > best_g.get(node, g):
                continue  # pragma: no cover - stale heap entry (lazy deletion)
            self._expand()
            for action, at, duration, succ, nfired, ng in task.timed_successors(state, fired, g):
                # g is the clock: each step costs its duration plus the gap
                # after it, so g of a path is its makespan + SEPARATION, and
                # ordering by g orders by makespan (#165)
                key = (succ, nfired)
                if ng < best_g.get(key, ng + 1.0):
                    best_g[key] = ng
                    came_from[key] = (node, action, at, duration)
                    heapq.heappush(frontier, (ng, next(counter), key))
        return None


register("temporal", TemporalPlanner)
