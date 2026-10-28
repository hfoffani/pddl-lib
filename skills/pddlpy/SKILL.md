---
name: pddlpy
description: Parse PDDL domain/problem files, solve them, and validate or simulate plans with pddlpy, via the pddlpy CLI (JSON output) or the Python API. Use when working with PDDL planning files — parsing a domain/problem, inspecting the initial state/goals/operators, grounding actions, evaluating numeric fluents or action costs, running a reference planner (BFS/A*/GBFS/UCS, or temporal for durative actions), or checking a plan (yours or another tool's) step by step.
---

# pddlpy

`pddlpy` parses PDDL into an object model and solves STRIPS-family problems
with built-in reference planners. It supports STRIPS, typing, ADL, numeric
fluents, action costs, and durative actions (sequential temporal planning).

## Setup

```bash
pip install pddlpy              # library + `pddlpy` CLI (or: uv pip install pddlpy)
pip install "pddlpy[mcp]"       # optional: also the MCP server (`pddlpy-mcp`)
```

The CLI/MCP/validate surface needs pddlpy >= 1.1; `uvx pddlpy ...` runs the
CLI with zero install. Working inside a checkout of the
[pddl-lib repo](https://github.com/hfoffani/pddl-lib) instead: `uv sync`,
then prefix commands with `uv run`.

Import: `from pddlpy import DomainProblem` and `from pddlpy.planning import get`.

## Quick path: the CLI (no Python needed)

Installing the package also installs a `pddlpy` command. For one-off
parse/ground/solve questions, prefer it over writing Python — JSON on stdout,
pipeable to `jq`:

```bash
pddlpy parse    domain.pddl problem.pddl            # object-model summary
pddlpy ground   domain.pddl problem.pddl move       # grounded instances of one action
pddlpy solve    domain.pddl problem.pddl --planner ucs   # default planner: astar
pddlpy validate domain.pddl problem.pddl            # diagnostics for PDDL you wrote
pddlpy validate-plan domain.pddl problem.pddl plan.txt   # does this plan reach the goal?
pddlpy simulate      domain.pddl problem.pddl plan.txt   # state after each step
pddlpy solve d.pddl p.pddl | pddlpy validate-plan d.pddl p.pddl -   # plan from stdin
```

**If you write or edit PDDL yourself** (e.g. translating a problem from
natural language), run `validate` before `solve` and fix what it reports:
it collects syntax errors (a bare parse error-recovers past them), atoms
over undeclared predicates, unknown objects, operators grounding to zero
instances, and malformed durative actions. Exit `0` = clean, `1` = issues
in the JSON `issues` list.

**Never trust a plan you produced by reasoning: check it with
`validate-plan`.** A plan file is one `(action arg ...)` per line (`;`
comments allowed), `time: (action arg ...) [duration]` for durative actions,
or the JSON `solve` prints. On failure the JSON `failure` gives `kind`
(`precondition`, `goal`, `unknown-action`, `arity`, `unknown-object`,
`type`, `duration`, `invariant`, `end-condition`, `mutex`,
`undefined-fluent`), the 1-based `step` and its `action`, the `unmet`
conditions (or goal atoms still false), and the `state` at that point: fix
that step and validate again. The semantics are VAL's: simultaneous
happenings (within 0.001) must not touch the same atoms, and a durative
step needs its `[duration]`.

Exit codes: `0` success, `1` search found no plan / validate found issues /
the plan is invalid or a step cannot run, `2` bad input (missing file,
unreadable plan, unknown operator/planner, unsupported `:requirements`, or a
plan pddlpy cannot judge — see Gotchas). Drop to the Python API below when
you need `State`/`GroundedTask`, custom binders, or anything the subcommands
don't cover. (The MCP server `pddlpy-mcp` exposes the same operations as
tools over stdio: `parse`, `ground`, `solve`, `validate`, `validate_plan`,
`simulate`; the plan tools take the plan text, not a path.)

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

plan = get("astar").solve(dp)   # or "bfs", "gbfs", "ucs", "temporal"
if plan is not None:
    print(plan.cost)            # accumulated total-cost, else action count
    print(plan.action_names())  # [(name, bindings), ...]
```

Planner choice: `bfs` (fewest actions), `astar` (goal-count heuristic; not
guaranteed optimal, use `bfs` for fewest actions), `gbfs` (greedy, fast), `ucs` (cost-optimal for `:action-costs`
domains), `temporal` (durative actions; returns a schedule with start times and
a `makespan`). A planner raises `UnsupportedRequirementsError` if a domain declares
`:requirements` it does not support.

## Validate or simulate a plan

```python
from pddlpy.planning import load_plan, simulate, validate_plan

steps = load_plan(open("plan.txt").read())   # IPC text or JSON
result = validate_plan(dp, steps)
if not result.valid:
    f = result.failure    # kind, message, step, action, time, unmet, state
sim = simulate(dp, steps) # sim.trace: (time, event, step, action, state) per happening
```

Both raise `PlanValidationError` when the plan cannot be read or judged.

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
- **Type hierarchies** are supported: a parameter typed with a supertype
  binds objects of any transitive subtype (`dp.types()` / `dp.subtypes_of(t)`
  expose the hierarchy). `(either ...)` union types parse but bind no objects.
- **Goals** must be a conjunction of positive atoms. `not`, `or`, `exists`,
  `forall` and numeric comparisons in `(:goal ...)` are misread without an
  error (e.g. `(not (p))` is read as `(p)`), so plans for such goals are wrong
  ([#138](https://github.com/hfoffani/pddl-lib/issues/138)). Not supported at all: `:derived-predicates`, `:constraints`,
  `:preferences` in goals, timed initial literals, duration inequalities,
  `:object-fluents`. `validate-plan` / `simulate` refuse (exit 2) what
  the model cannot represent instead of guessing: syntax errors, goals that
  are not a conjunction of atoms, durative actions with numeric, conditional
  or quantified parts or duration inequalities. Full status per requirement:
  [docs/pddl-support.md](https://github.com/hfoffani/pddl-lib/blob/main/docs/pddl-support.md).
- **Durative actions** (`:durative-actions`) parse into `DurativeAction`
  (`dp.durative_operators()`) and are solved only by `temporal`, under
  sequential semantics: domains that require overlapping actions are not solved.
- Uppercase keywords (`(:INIT ...)`) are fine — keywords are case-insensitive;
  identifiers keep their case.

## Developing pddl-lib itself (repo checkout only)

```bash
make            # grammar + python tests
make coverage   # tests with coverage
make lint       # ruff
make typecheck  # mypy
```

Full model reference:
[docs/object-model.md](https://github.com/hfoffani/pddl-lib/blob/main/docs/object-model.md).
