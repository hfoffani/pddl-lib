"""Playground scenarios: an English problem plus its reference PDDL.

A scenario is a directory under ``e2e/llm/scenarios/``:

    problem.md    the text the model sees (read it, tweak it)
    domain.pddl   reference domain  } used only to grade answers and to
    problem.pddl  reference problem } check the optimum; never shown to the model
    meta.json     {"optimal_cost": N, "planner": "ucs", "source": "..."}
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from typing import List, Optional

from pddlpy import DomainProblem
from pddlpy.planning import plan_cost, plan_steps, solve
from pddlpy.planning.state import State

ROOT = pathlib.Path(__file__).parent / "scenarios"


@dataclass
class Scenario:
    name: str
    path: pathlib.Path
    text: str
    optimal_cost: float
    planner: str
    source: str

    @property
    def domain_file(self) -> pathlib.Path:
        return self.path / "domain.pddl"

    @property
    def problem_file(self) -> pathlib.Path:
        return self.path / "problem.pddl"

    def reference(self) -> DomainProblem:
        return DomainProblem(str(self.domain_file), str(self.problem_file))


def load(name: str, root: pathlib.Path = ROOT) -> Scenario:
    path = root / name
    if not (path / "problem.md").is_file():
        raise SystemExit("no scenario %r (see `playground.py list`)" % name)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    return Scenario(name, path, (path / "problem.md").read_text(encoding="utf-8").strip(),
                    float(meta["optimal_cost"]), meta.get("planner", "ucs"),
                    meta.get("source", ""))


def all_scenarios(root: pathlib.Path = ROOT) -> List[Scenario]:
    return [load(p.name, root) for p in sorted(root.iterdir())
            if (p / "problem.md").is_file()]


@dataclass
class Check:
    cost: Optional[float]
    seconds: float
    plan: List[str]
    message: str


def check(sc: Scenario, timeout: float = 60.0) -> Check:
    """Solve the reference problem with the scenario's (optimal) planner."""
    dp = sc.reference()
    t0 = time.monotonic()
    res = solve(dp, sc.planner, timeout=timeout)
    secs = time.monotonic() - t0
    if res.plan is None:
        return Check(None, secs, [], res.message or res.status)
    steps = plan_steps(dp, res.plan)
    return Check(float(res.plan.cost), secs, [str(s) for s in steps], res.message)


def final_cost(state: State, n_steps: int) -> float:
    """Plan cost the way pddlpy's planners count it."""
    return float(plan_cost(state, [None] * n_steps))  # type: ignore[list-item]
