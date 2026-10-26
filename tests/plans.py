"""Plan fixtures for the IPC subset (#153): a valid plan and corrupted ones.

For each subset pair that pddlpy's ``bfs`` solves within the time budget,
``plans/pNN.plan`` holds the plan and ``plans/pNN.<corruption>.plan`` the
corrupted variants. ``bfs`` returns a shortest plan, so each corruption is
invalid by construction:

  drop-first, drop-last  -- a shorter valid plan cannot exist
  unknown-action         -- the first step names an action the domain lacks
  unknown-object         -- the first step's first argument is not an object

They are the reference cases for plan validation against VAL/INVAL (step 3
of the roadmap). Regenerate with ``make golden``.
"""
from __future__ import annotations

import os
import signal
from typing import Any, Dict, List

from golden import pairs
from oracles import Step, plan_steps, write_plan

from pddlpy import DomainProblem
from pddlpy.planning import get

BUDGET = 20  # seconds of bfs per pair


def plans_dir(problem: str) -> str:
    return os.path.join(os.path.dirname(problem), "plans")


def corruptions(steps: List[Step]) -> Dict[str, List[Step]]:
    name, args = steps[0]
    return {
        "drop-first": steps[1:],
        "drop-last": steps[:-1],
        "unknown-action": [("no-such-action", args)] + steps[1:],
        "unknown-object": [(name, ("no-such-object",) + args[1:])] + steps[1:],
    }


class _Timeout(Exception):
    pass


def _alarm(*_: Any) -> None:
    raise _Timeout()


def fixtures() -> List[str]:
    """Paths of every valid plan fixture (``plans/pNN.plan``), sorted."""
    found = []
    for _, problem in pairs():
        stem = os.path.splitext(os.path.basename(problem))[0]
        path = os.path.join(plans_dir(problem), stem + ".plan")
        if os.path.exists(path):
            found.append(path)
    return found


def main() -> None:
    signal.signal(signal.SIGALRM, _alarm)
    for domain, problem in pairs():
        signal.alarm(BUDGET)
        try:
            dp = DomainProblem(domain, problem)
            if dp.durative_operators():
                continue
            plan = get("bfs").solve(dp)
        except Exception:  # timeout, refused requirements, loader crash
            continue
        finally:
            signal.alarm(0)
        if not plan:  # unsolvable, or empty: nothing to corrupt
            continue
        steps = plan_steps(dp, plan)
        out = plans_dir(problem)
        os.makedirs(out, exist_ok=True)
        stem = os.path.splitext(os.path.basename(problem))[0]
        write_plan(steps, os.path.join(out, stem + ".plan"))
        for kind, bad in corruptions(steps).items():
            write_plan(bad, os.path.join(out, "%s.%s.plan" % (stem, kind)))
        print(os.path.relpath(os.path.join(out, stem + ".plan")))


if __name__ == "__main__":
    main()
