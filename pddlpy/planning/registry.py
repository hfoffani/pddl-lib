"""Planner registry (PRD §5.4).

    from pddlpy.planning import registry
    registry.register("astar", AStarPlanner)
    planner = registry.get("astar")     # -> an AStarPlanner instance
    plan = planner.solve(domainproblem)
"""


class PlannerRegistry:
    """Maps short names to ``Planner`` subclasses."""

    def __init__(self):
        self._planners = {}

    def register(self, name, planner_cls):
        self._planners[name] = planner_cls

    def get(self, name, *args, **kwargs):
        """Return a new planner instance registered under ``name``."""
        if name not in self._planners:
            raise KeyError(
                "no planner registered as %r; known: %s"
                % (name, sorted(self._planners))
            )
        return self._planners[name](*args, **kwargs)

    def names(self):
        return sorted(self._planners)


registry = PlannerRegistry()


def register(name, planner_cls):
    """Register ``planner_cls`` under ``name`` in the default registry."""
    registry.register(name, planner_cls)


def get(name, *args, **kwargs):
    """Get a planner instance from the default registry."""
    return registry.get(name, *args, **kwargs)
