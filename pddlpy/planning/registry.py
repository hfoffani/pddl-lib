"""Planner registry (PRD §5.4).

    from pddlpy.planning import registry
    registry.register("astar", AStarPlanner)
    planner = registry.get("astar")     # -> an AStarPlanner instance
    plan = planner.solve(domainproblem)
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Type

if TYPE_CHECKING:
    from .base import Planner


class PlannerRegistry:
    """Maps short names to ``Planner`` subclasses."""

    def __init__(self) -> None:
        self._planners: Dict[str, Type["Planner"]] = {}

    def register(self, name: str, planner_cls: Type["Planner"]) -> None:
        self._planners[name] = planner_cls

    def get(self, name: str, *args: Any, **kwargs: Any) -> "Planner":
        """Return a new planner instance registered under ``name``."""
        if name not in self._planners:
            raise KeyError(
                "no planner registered as %r; known: %s"
                % (name, sorted(self._planners))
            )
        return self._planners[name](*args, **kwargs)

    def names(self) -> List[str]:
        return sorted(self._planners)


registry = PlannerRegistry()


def register(name: str, planner_cls: Type["Planner"]) -> None:
    """Register ``planner_cls`` under ``name`` in the default registry."""
    registry.register(name, planner_cls)


def get(name: str, *args: Any, **kwargs: Any) -> "Planner":
    """Get a planner instance from the default registry."""
    return registry.get(name, *args, **kwargs)
