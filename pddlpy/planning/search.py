"""Blind- and heuristic-search reference planners over STRIPS.

These prove the ``Planner`` contract; they are not performance entrants
(PRD §4). All three reuse the shared ``GroundedTask`` successor function.

* ``BFSPlanner``   — breadth-first; optimal for unit-cost STRIPS.
* ``AStarPlanner`` — A* with the goal-count heuristic; optimal & admissible
  for unit costs.
* ``GBFSPlanner``  — greedy best-first; fast but not optimal.
"""
import heapq
import itertools
from collections import deque

from .base import Planner
from .state import Plan, atom_tuple
from .registry import register

#: Requirements the reference STRIPS planners can handle.
STRIPS_CAPABILITIES = frozenset(
    {":strips", ":typing", ":negative-preconditions", ":equality"}
)


def _reconstruct(came_from, state):
    """Walk parent pointers back to the start, returning the action list."""
    actions = []
    while state in came_from:
        prev, action = came_from[state]
        actions.append(action)
        state = prev
    actions.reverse()
    return actions


def goal_count(goal_atoms, state):
    """Heuristic: number of goal atoms not yet satisfied (admissible for
    unit costs)."""
    return len(goal_atoms - state.atoms)


class BFSPlanner(Planner):
    """Breadth-first search. Returns a shortest (fewest-action) plan."""

    capabilities = STRIPS_CAPABILITIES

    def solve(self, domainproblem):
        task = self.prepare(domainproblem)
        start = task.initial
        if task.is_goal(start):
            return Plan([])
        frontier = deque([start])
        visited = {start}
        came_from = {}
        while frontier:
            state = frontier.popleft()
            for action, succ in task.successors(state):
                if succ in visited:
                    continue
                came_from[succ] = (state, action)
                if task.is_goal(succ):
                    return Plan(_reconstruct(came_from, succ))
                visited.add(succ)
                frontier.append(succ)
        return None


class _BestFirstPlanner(Planner):
    """Shared best-first core; subclasses define the node priority."""

    capabilities = STRIPS_CAPABILITIES

    def _priority(self, g, h):
        raise NotImplementedError

    def solve(self, domainproblem):
        task = self.prepare(domainproblem)
        goal_atoms = frozenset(atom_tuple(a) for a in task.goals)
        start = task.initial
        counter = itertools.count()  # tie-breaker; keeps States out of compares
        h0 = goal_count(goal_atoms, start)
        frontier = [(self._priority(0, h0), 0, next(counter), start)]
        best_g = {start: 0}
        came_from = {}
        while frontier:
            _, g, _, state = heapq.heappop(frontier)
            if task.is_goal(state):
                return Plan(_reconstruct(came_from, state))
            if g > best_g.get(state, g):
                continue  # stale entry
            for action, succ in task.successors(state):
                ng = g + 1
                if ng < best_g.get(succ, ng + 1):
                    best_g[succ] = ng
                    came_from[succ] = (state, action)
                    h = goal_count(goal_atoms, succ)
                    heapq.heappush(
                        frontier, (self._priority(ng, h), ng, next(counter), succ)
                    )
        return None


class AStarPlanner(_BestFirstPlanner):
    """A* with the goal-count heuristic (f = g + h)."""

    def _priority(self, g, h):
        return g + h


class GBFSPlanner(_BestFirstPlanner):
    """Greedy best-first search (f = h)."""

    def _priority(self, g, h):
        return h


register("bfs", BFSPlanner)
register("astar", AStarPlanner)
register("gbfs", GBFSPlanner)
