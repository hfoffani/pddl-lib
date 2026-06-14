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

from .base import Planner
from .state import Plan, State, atom_tuple
from .registry import register
from .costs import action_cost, plan_cost

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem, Operator
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

    capabilities = STRIPS_CAPABILITIES

    def solve(self, domainproblem: "DomainProblem") -> Optional[Plan]:
        task = self.prepare(domainproblem)
        start = task.initial
        if task.is_goal(start):
            return Plan([])
        frontier: "deque[State]" = deque([start])
        visited = {start}
        came_from: _CameFrom = {}
        while frontier:
            state = frontier.popleft()
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

    capabilities = STRIPS_CAPABILITIES

    def _priority(self, g: float, h: float) -> float:
        raise NotImplementedError  # pragma: no cover - abstract

    def _step_cost(self, action: "Operator", state: State) -> float:
        """Cost of one transition. Unit by default; cost-aware planners
        override."""
        return 1

    def solve(self, domainproblem: "DomainProblem") -> Optional[Plan]:
        task = self.prepare(domainproblem)
        goal_atoms = frozenset(atom_tuple(a) for a in task.goals)
        start = task.initial
        counter = itertools.count()  # tie-breaker; keeps States out of compares
        h0 = goal_count(goal_atoms, start)
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
            for action, succ in task.successors(state):
                ng = g + self._step_cost(action, state)
                if ng < best_g.get(succ, ng + 1):
                    best_g[succ] = ng
                    came_from[succ] = (state, action)
                    h = goal_count(goal_atoms, succ)
                    heapq.heappush(
                        frontier, (self._priority(ng, h), ng, next(counter), succ)
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
    none."""

    def _priority(self, g: float, h: float) -> float:
        return g

    def _step_cost(self, action: "Operator", state: State) -> float:
        return action_cost(action, state)


register("bfs", BFSPlanner)
register("astar", AStarPlanner)
register("gbfs", GBFSPlanner)
register("ucs", UniformCostPlanner)
