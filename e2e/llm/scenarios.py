"""Playground scenarios: an English problem plus its reference PDDL.

A scenario is a directory under ``e2e/llm/scenarios/``:

    problem.md    the text the model sees (read it, tweak it)
    domain.pddl   reference domain  } used only to grade answers and to
    problem.pddl  reference problem } check the optimum; never shown to the model
    meta.json     {"optimal_cost": N, "planner": "ucs", "source": "..."}

``meta.json`` may set ``kind``:

    solve         (default) find a cheapest plan; graded against optimal_cost
    improve-plan  problem.md shows a valid but suboptimal plan
                  (proposed.plan); graded like solve
    check-plan    problem.md shows a plan (proposed.plan) that first fails at
                  step ``first_bad_step``; the answer ends with a
                  ``VERDICT:`` line
    unsolvable    no plan exists (no optimal_cost); the answer must say so

``"planner": "none"`` marks a scenario too large for the reference check:
``check`` then validates ``optimal.plan`` at ``optimal_cost`` instead of
solving (its minimality comes from the generator, see ``source``).
"""
from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass
from typing import List, Optional

from pddlpy import DomainProblem
from pddlpy.planning import parse_plan, plan_cost, plan_steps, solve, validate_plan
from pddlpy.planning.state import State

ROOT = pathlib.Path(__file__).parent / "scenarios"


@dataclass
class Scenario:
    name: str
    path: pathlib.Path
    text: str
    optimal_cost: Optional[float]
    planner: str
    source: str
    kind: str = "solve"
    first_bad_step: Optional[int] = None

    @property
    def domain_file(self) -> pathlib.Path:
        return self.path / "domain.pddl"

    @property
    def problem_file(self) -> pathlib.Path:
        return self.path / "problem.pddl"

    @property
    def proposed_file(self) -> pathlib.Path:
        return self.path / "proposed.plan"

    def reference(self) -> DomainProblem:
        return DomainProblem(str(self.domain_file), str(self.problem_file))


def load(name: str, root: pathlib.Path = ROOT) -> Scenario:
    path = root / name
    if not (path / "problem.md").is_file():
        raise SystemExit("no scenario %r (see `playground.py list`)" % name)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    opt = meta.get("optimal_cost")
    return Scenario(name, path, (path / "problem.md").read_text(encoding="utf-8").strip(),
                    None if opt is None else float(opt), meta.get("planner", "ucs"),
                    meta.get("source", ""), meta.get("kind", "solve"),
                    meta.get("first_bad_step"))


def all_scenarios(root: pathlib.Path = ROOT) -> List[Scenario]:
    return [load(p.name, root) for p in sorted(root.iterdir())
            if (p / "problem.md").is_file()]


@dataclass
class Check:
    cost: Optional[float]
    seconds: float
    plan: List[str]
    message: str
    ok: bool = False


def check(sc: Scenario, timeout: float = 60.0) -> Check:
    """Solve the reference problem with the scenario's (optimal) planner.
    ``ok``: the result matches ``meta.json`` (the optimum; no plan for
    ``unsolvable``; for ``check-plan`` the proposed plan first fails at
    ``first_bad_step``)."""
    dp = sc.reference()
    t0 = time.monotonic()
    if sc.planner == "none":
        text = (sc.path / "optimal.plan").read_text(encoding="utf-8")
        v = validate_plan(dp, parse_plan(text))
        cost = final_cost(v.simulation.state, len(text.split("\n")) - 1) if v.valid else None
        ok = cost is not None and abs(cost - (sc.optimal_cost or 0)) < 1e-9
        return Check(cost, time.monotonic() - t0, text.split("\n")[:-1],
                     "optimal.plan, not solved", ok)
    res = solve(dp, sc.planner, timeout=timeout)
    secs = time.monotonic() - t0
    if res.plan is None:
        ok = sc.kind == "unsolvable" and res.status == "unsolvable"
        return Check(None, secs, [], res.message or res.status, ok)
    steps = plan_steps(dp, res.plan)
    cost = float(res.plan.cost)
    ok = sc.optimal_cost is not None and abs(cost - sc.optimal_cost) < 1e-9
    message = res.message
    if sc.kind == "check-plan":
        v = validate_plan(dp, parse_plan(sc.proposed_file.read_text(encoding="utf-8")))
        bad = None if v.valid else v.failure.step  # type: ignore[union-attr]
        ok = bad == sc.first_bad_step
        message = "; ".join(x for x in (message, "proposed plan fails at step %s" % bad) if x)
    return Check(cost, secs, [str(s) for s in steps], message, ok)


def final_cost(state: State, n_steps: int) -> float:
    """Plan cost the way pddlpy's planners count it."""
    return float(plan_cost(state, [None] * n_steps))  # type: ignore[list-item]
