"""Blind- and heuristic-search reference planners over STRIPS.

These prove the ``Planner`` contract; they are not performance entrants
(PRD §4). All reuse the shared ``GroundedTask`` successor function.

* ``BFSPlanner``        — breadth-first; optimal for unit-cost STRIPS.
* ``AStarPlanner``      — A* with the goal-count heuristic; optimal &
  admissible for unit costs.
* ``GBFSPlanner``       — greedy best-first; fast but not optimal.
* ``UniformCostPlanner`` — Dijkstra over action costs; cost-optimal for
  action-cost domains (#3).
"""
from __future__ import annotations

import heapq
import itertools
from collections import deque
from typing import TYPE_CHECKING, Dict, FrozenSet, List, Optional, Tuple

from .base import Planner, UnsupportedRequirementsError
from .costs import TOTAL_COST, action_cost, plan_cost
from .registry import register
from .state import Plan, State, atom_tuple, goal_holds, preference_undefined

if TYPE_CHECKING:
    from pddlpy.pddl import Condition, DomainProblem, Operator

    from .state import GroundAtom

#: Parent-pointer map used to reconstruct a plan.
_CameFrom = Dict[State, Tuple[State, "Operator"]]

#: Requirements the reference planners can handle. Numeric fluents (#11) and
#: action costs (#3) are supported because State evaluates numeric
#: preconditions/effects during successor generation; the goal-count heuristic
#: ignores them (still admissible for the symbolic goal).
STRIPS_CAPABILITIES: FrozenSet[str] = frozenset(
    {":strips", ":typing", ":negative-preconditions", ":equality",
     ":fluents", ":numeric-fluents", ":action-costs"}
)

#: ADL (#10) adds full boolean/quantified/equality preconditions and
#: conditional/universal effects. State.applicable evaluates the grounded
#: precondition tree and State.apply fires conditional effects, so the
#: reference planners can now solve ADL domains, and derived predicates
#: (#141) are recomputed in every state. Durative actions
#: (:durative-actions) remain out of scope.
ADL_CAPABILITIES: FrozenSet[str] = STRIPS_CAPABILITIES | frozenset(
    {":adl", ":disjunctive-preconditions", ":conditional-effects",
     ":universal-preconditions", ":existential-preconditions",
     ":quantified-preconditions", ":derived-predicates"}
)


def _reconstruct(came_from: _CameFrom, state: State) -> List["Operator"]:
    """Walk parent pointers back to the start, returning the action list."""
    actions: List["Operator"] = []
    while state in came_from:
        prev, action = came_from[state]
        actions.append(action)
        state = prev
    actions.reverse()
    return actions


def goal_count(goal_atoms: "FrozenSet[GroundAtom]", state: State) -> int:
    """Heuristic: number of goal atoms not yet satisfied (admissible for
    unit costs)."""
    return len(goal_atoms - state.atoms)


class BFSPlanner(Planner):
    """Breadth-first search. Returns a shortest (fewest-action) plan."""

    capabilities = ADL_CAPABILITIES

    def solve(self, domainproblem: "DomainProblem") -> Optional[Plan]:
        task = self.prepare(domainproblem)
        self._start_search()
        start = task.initial
        if task.is_goal(start):
            return Plan([])
        frontier: "deque[State]" = deque([start])
        visited = {start}
        came_from: _CameFrom = {}
        while frontier:
            state = frontier.popleft()
            self._expand()
            for action, succ in task.successors(state):
                if succ in visited:
                    continue
                came_from[succ] = (state, action)
                if task.is_goal(succ):
                    actions = _reconstruct(came_from, succ)
                    return Plan(actions, cost=plan_cost(succ, actions))
                visited.add(succ)
                frontier.append(succ)
        return None


class _BestFirstPlanner(Planner):
    """Shared best-first core; subclasses define the node priority and the
    per-step cost."""

    capabilities = ADL_CAPABILITIES

    def _priority(self, g: float, h: float) -> float:
        raise NotImplementedError  # pragma: no cover - abstract

    def _step_cost(self, action: "Operator", state: State) -> float:
        """Cost of one transition. Unit by default; cost-aware planners
        override."""
        return 1

    def solve(self, domainproblem: "DomainProblem") -> Optional[Plan]:
        task = self.prepare(domainproblem)
        self._start_search()
        goal_atoms = frozenset(atom_tuple(a) for a in task.goals)
        simple = domainproblem.problem.simple_goal

        def h(state: State) -> int:
            # goal-count needs a conjunction of atoms; any other goal (#138)
            # gets the blind heuristic: 0 at a goal, else 1 (admissible).
            return goal_count(goal_atoms, state) if simple else int(not task.is_goal(state))

        start = task.initial
        counter = itertools.count()  # tie-breaker; keeps States out of compares
        h0 = h(start)
        frontier: List[Tuple[float, float, int, State]] = [
            (self._priority(0, h0), 0, next(counter), start)
        ]
        best_g: Dict[State, float] = {start: 0}
        came_from: _CameFrom = {}
        while frontier:
            _, g, _, state = heapq.heappop(frontier)
            if task.is_goal(state):
                actions = _reconstruct(came_from, state)
                return Plan(actions, cost=plan_cost(state, actions))
            if g > best_g.get(state, g):
                continue  # pragma: no cover - stale heap entry (lazy deletion)
            self._expand()
            for action, succ in task.successors(state):
                ng = g + self._step_cost(action, state)
                if ng < best_g.get(succ, ng + 1):
                    best_g[succ] = ng
                    came_from[succ] = (state, action)
                    heapq.heappush(
                        frontier, (self._priority(ng, h(succ)), ng, next(counter), succ)
                    )
        return None


class AStarPlanner(_BestFirstPlanner):
    """A* with the goal-count heuristic (f = g + h), unit step cost."""

    def _priority(self, g: float, h: float) -> float:
        return g + h


class GBFSPlanner(_BestFirstPlanner):
    """Greedy best-first search (f = h)."""

    def _priority(self, g: float, h: float) -> float:
        return h


class UniformCostPlanner(_BestFirstPlanner):
    """Dijkstra over action costs (f = g, h ignored). Cost-optimal for
    action-cost domains (#3); falls back to unit cost when a domain declares
    none. With goal preferences (#201) it minimizes the metric instead."""

    capabilities = ADL_CAPABILITIES | {":preferences"}
    preferences = True

    def _priority(self, g: float, h: float) -> float:
        return g

    def _step_cost(self, action: "Operator", state: State) -> float:
        return action_cost(action, state)

    def solve(self, domainproblem: "DomainProblem") -> Optional[Plan]:
        if not domainproblem.problem.preferences:
            return super().solve(domainproblem)
        return self._solve_preferences(domainproblem)

    def _solve_preferences(self, domainproblem: "DomainProblem") -> Optional[Plan]:
        """Minimize ``c * total-cost + sum(w * violated)`` (#201): the soft
        goals compiled to action costs (Keyder & Geffner 2009). Each state
        that reaches the hard goal gets a terminal node priced with the
        violations it leaves, the price of the forgo actions; the first
        terminal popped is optimal."""
        task = self.prepare(domainproblem)
        c, weighted = _preference_metric(domainproblem)
        self._start_search()

        def spent(state: State) -> float:
            return state.fluents.get(TOTAL_COST, 0.0)

        # with c == 0 the accumulated cost is irrelevant: keep it out of the
        # state, or an action that only adds cost makes the search endless
        if not c and _reads_total_cost(domainproblem):
            raise UnsupportedRequirementsError(
                "a condition reads (total-cost) but the metric ignores it, so "
                "the search may not end; weigh (total-cost) in the metric (#201)")

        def key(state: State) -> State:
            if c:
                return state
            return State(state.atoms, {f: v for f, v in state.fluents.items() if f != TOTAL_COST})

        soft = [g for pref in domainproblem.problem.preferences for g in pref.ground(domainproblem)]

        def defined(state: State) -> bool:
            # VAL fails a plan whose preferences read a fluent with no value
            return not any(preference_undefined(g, state) for g in soft)

        def penalty(state: State) -> float:
            return sum(w * sum(not goal_holds(g, state) for g in instances)
                       for w, instances in weighted)

        start = key(task.initial)
        counter = itertools.count()
        # (priority, tiebreak, state, terminal, g: the total-cost spent)
        frontier: List[Tuple[float, int, State, bool, float]] = [
            (0.0, next(counter), start, False, 0.0)]
        best: Dict[State, float] = {start: 0.0}
        came_from: _CameFrom = {}
        while frontier:
            priority, _, state, terminal, g = heapq.heappop(frontier)
            if terminal:
                actions = _reconstruct(came_from, state)
                return Plan(actions, cost=g if TOTAL_COST in task.initial.fluents
                            else len(actions))
            if priority > best.get(state, priority):
                continue  # pragma: no cover - stale heap entry (lazy deletion)
            if task.is_goal(state) and defined(state):
                heapq.heappush(frontier, (priority + penalty(state), next(counter),
                                          state, True, g))
            self._expand()
            for action, succ in task.successors(state):
                # the metric counts the total-cost actually spent: an action
                # with no cost effect is free here, not the unit fallback
                ng = g + spent(succ) - spent(state)
                succ = key(succ)
                npriority = c * ng
                if npriority < best.get(succ, npriority + 1):
                    best[succ] = npriority
                    came_from[succ] = (state, action)
                    heapq.heappush(frontier, (npriority, next(counter), succ, False, ng))
        return None


def _reads_total_cost(dp: "DomainProblem") -> bool:
    """True if a precondition, effect expression, the goal or a preference
    reads ``(total-cost)``; increasing it is a write, not a read."""
    from pddlpy.pddl import Fluent, NumericEffect

    def reads(node: object) -> bool:
        if isinstance(node, Fluent):
            return node.head == TOTAL_COST
        if isinstance(node, NumericEffect):
            return reads(node.expr)
        if isinstance(node, (list, tuple)):
            return any(reads(n) for n in node)
        return hasattr(node, "__dict__") and any(reads(v) for v in vars(node).values())

    ops = dp.domain.operators.values()
    return reads([dp.problem.goal, [p.body for p in dp.problem.preferences],
                  [r.body for r in dp.domain.derived],
                  [(op.precondition_tree, op.effect_tree) for op in ops]])


def _preference_metric(dp: "DomainProblem") -> Tuple[float, List[Tuple[float, List[Condition]]]]:
    """``(c, [(w, instances)])`` of a metric ``c * total-cost + sum(w *
    (is-violated p))`` to minimize (#201), each preference's grounded
    instances with its weight. Raises :class:`UnsupportedRequirementsError`
    for a metric of another shape or with negative coefficients."""
    form = dp.problem.metric_form
    metric = dp.metric()
    optimization = metric[0] if metric else "minimize"
    if form is None:
        form = {}  # no metric: every preference weighs nothing
        if metric:
            raise UnsupportedRequirementsError(
                "the metric must be linear in (total-cost) and (is-violated ...) "
                "for preferences (#201)")
    sign = 1.0 if optimization == "minimize" else -1.0
    c = sign * form.get("total-cost", 0.0)
    weighted = []
    for pref in dp.problem.preferences:
        w = sign * form.get("is-violated %s" % pref.name, 0.0)
        if w:
            weighted.append((w, pref.ground(dp)))
    if c < 0 or any(w < 0 for w, _ in weighted):
        raise UnsupportedRequirementsError(
            "the metric must not reward cost or violated preferences (#201)")
    return c, weighted


register("bfs", BFSPlanner)
register("astar", AStarPlanner)
register("gbfs", GBFSPlanner)
register("ucs", UniformCostPlanner)
