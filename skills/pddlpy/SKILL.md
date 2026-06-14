---
name: pddlpy
description: Parse PDDL domain/problem files and solve them with pddlpy. Use when working with PDDL planning files — parsing a domain/problem, inspecting the initial state/goals/operators, grounding actions, evaluating numeric fluents or action costs, or running a reference planner (BFS/A*/GBFS/UCS) to produce a plan.
---

# pddlpy

`pddlpy` parses PDDL into an object model and solves STRIPS-family problems
with built-in reference planners. It supports STRIPS, typing, numeric fluents,
and action costs; durative actions are parsed but not solved.

## Setup

```bash
uv sync          # install (project uses uv)
```

Import: `from pddlpy import DomainProblem` and `from pddlpy.planning import get`.

## Parse a domain + problem

```python
from pddlpy import DomainProblem

dp = DomainProblem("domain.pddl", "problem.pddl")
dp.initialstate()      # set of Atom (initial facts)
dp.goals()             # set of Atom (goal facts)
list(dp.operators())   # action names
dp.requirements()      # e.g. {":strips", ":typing"}
dp.functions()         # numeric :functions, if any
dp.metric()            # ("minimize", "(total-cost)") or None
```

## Ground an operator

```python
for op in dp.ground_operator("move"):
    op.variable_list        # {"?from": "a", "?to": "b"}
    op.precondition_pos     # set of ground atom tuples
    op.effect_pos / op.effect_neg
    op.precondition_num / op.effect_num   # numeric (NumericConstraint / NumericEffect)
```

## Solve

```python
from pddlpy.planning import get

plan = get("astar").solve(dp)   # or "bfs", "gbfs", "ucs"
if plan is not None:
    print(plan.cost)            # accumulated total-cost, else action count
    print(plan.action_names())  # [(name, bindings), ...]
```

Planner choice: `bfs` (fewest actions), `astar` (goal-count heuristic, optimal
for unit costs), `gbfs` (greedy, fast), `ucs` (cost-optimal for `:action-costs`
domains). A planner raises `UnsupportedRequirementsError` if a domain declares
`:requirements` it does not support.

## Work with states directly

```python
from pddlpy.planning import State, GroundedTask

task = GroundedTask(dp)
s = task.initial
for action, succ in task.successors(s):   # applicable actions + next states
    ...
task.is_goal(s)
s.applicable(op); s.apply(op)              # no manual Atom/tuple casting
```

## Gotchas

- `initialstate()`/`goals()` return `Atom` objects with **no value equality**.
  A grounded operator's pre/effects are plain tuples. Normalize with
  `from pddlpy.planning import atom_tuple` (or compare `repr`s / use `State`).
- **Type hierarchies (#22):** grounding matches a parameter's declared type
  exactly — multi-level hierarchies (e.g. logistics) do not fully ground.
  Untyped (blocksworld) and single-level typed (gripper) domains work.
- **Durative actions** (`:durative-actions`) parse into `DurativeAction`
  (`dp.durative_operators()`), but the reference planners are non-temporal and
  will not solve them.
- Uppercase keywords (`(:INIT ...)`) are fine — keywords are case-insensitive;
  identifiers keep their case.

## Commands

```bash
make            # grammar + python tests
make coverage   # tests with coverage
make lint       # ruff
make typecheck  # mypy
```

See `docs/object-model.md` for the full model reference.
