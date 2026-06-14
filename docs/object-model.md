# pddlpy object model

This document describes the object model produced by parsing a PDDL
domain/problem pair, and the planning layer built on top of it. For a quick
start see the [README](../README.md); for agent-oriented usage see
[`skills/pddlpy/SKILL.md`](../skills/pddlpy/SKILL.md).

```
ANTLR4 grammar -> parse tree -> listener -> object model -> planning layer
   pddl.g4          (generated)  DomainListener/   DomainProblem    pddlpy.planning
                                 ProblemListener   Operator/Atom/…
```

## Layers

| Layer | Module | Depends on |
|-------|--------|-----------|
| Grammar / parser | `pddlLexer`, `pddlParser`, `pddlListener` (generated from `pddl.g4`) | — |
| Object model | `pddlpy.pddl` | grammar |
| Planning | `pddlpy.planning` | object model only (never the grammar) |

The boundary is enforced by a test: no planning module imports the grammar,
and the model imports nothing from the planning layer.

## Object model (`pddlpy.pddl`)

### `DomainProblem(domainfile, problemfile)`
The entry point. Parses both files and exposes:

| Method | Returns |
|--------|---------|
| `initialstate()` | set of `Atom` — the problem's initial facts |
| `goals()` | set of `Atom` — the (positive) goal facts |
| `operators()` | names of the instantaneous actions |
| `ground_operator(name)` | iterator of grounded `Operator` instances |
| `durative_operators()` | names of the durative actions (#23) |
| `ground_durative_operator(name)` | iterator of grounded `DurativeAction` |
| `worldobjects()` | `{object: type or None}` |
| `requirements()` | declared `:requirements` (e.g. `{":strips", ":typing"}`) |
| `functions()` | `:functions` → ordered `(param, type)` list |
| `initial_numeric()` | `{ground function head: value}` |
| `metric()` | `(optimization, expr_text)` or `None` |

### `Atom`
A predicate applied to terms, e.g. `(on ?x ?y)`. `predicate` is
`[name, *terms]`; `ground(varvals)` substitutes variables and returns a plain
tuple. **`Atom` has no value equality** — `initialstate()`/`goals()` hold
`Atom` objects, while a *grounded* `Operator`'s precondition/effect sets hold
tuples. Normalize with `pddlpy.planning.atom_tuple` (or compare `repr`s).

### `Operator`
An instantaneous action, grounded or not. Fields: `operator_name`,
`variable_list`, `precondition_pos`/`precondition_neg`,
`precondition_connective` (`'and'`/`'or'`, #13), `effect_pos`/`effect_neg`,
and the numeric `precondition_num`/`effect_num` (#11).

### Numeric fluents (#11)
`Expr` tree — `Num`, `Fluent`, `BinOp`, `Neg` — each with
`ground(varvals)` and `value(valuation)`. `NumericConstraint.holds(valuation)`
evaluates a numeric precondition; `NumericEffect.apply(valuation)` returns the
`(head, new_value)` an effect produces.

### `DurativeAction` (#23)
A durative action with time-tagged `condition_pos`/`condition_neg` keyed by
`'start'`/`'over'`/`'end'`, `effect_pos`/`effect_neg` keyed by
`'start'`/`'end'`, and a `duration`. Recovered into the model but **not**
solved by the reference planners (they are non-temporal).

## Planning layer (`pddlpy.planning`)

- **`State`** — immutable, hashable set of ground atoms plus a numeric fluent
  valuation. `State.from_problem(dp)`, `state.applicable(op)`,
  `state.apply(op)`, `state.satisfies(goals)`.
- **`Plan`** — ordered grounded actions with a `cost`.
- **`GroundedTask`** — grounds every operator once; `successors(state)` and
  `is_goal(state)`. Shared by all planners.
- **`Planner`** ABC — `solve(domainproblem) -> Plan | None`, with a
  `capabilities` set and fail-fast capability/`:requirements` checks (#9).
- **`registry`** — register/get planners by name.
- **Reference planners** — `bfs`, `astar` (goal-count heuristic), `gbfs`,
  `ucs` (cost-optimal, #3).

```python
from pddlpy import DomainProblem
from pddlpy.planning import get

dp = DomainProblem("domain.pddl", "problem.pddl")
plan = get("astar").solve(dp)
print(plan.cost, plan.action_names())
```

## Known limitations

- **Type hierarchies (#22):** grounding matches a parameter's declared type
  exactly, so multi-level type hierarchies (e.g. logistics) do not fully
  ground. Single-level typing (gripper) and untyped domains (blocksworld)
  work.
- **Disjunctive/ADL preconditions:** the `or` connective is preserved but not
  evaluated; the reference planners reject such domains via capability checks.
- **Durative actions:** recovered into the model but not solved (non-temporal
  planners).
