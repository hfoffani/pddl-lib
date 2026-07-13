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
| `predicates()` | set of declared predicate names |
| `types()` | `{type: supertype or None}` — the `:types` hierarchy (#22) |
| `subtypes_of(t)` | `t` plus all its transitive subtypes |
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
An instantaneous action, grounded or not. The flat STRIPS-style fields —
`operator_name`, `variable_list`, `precondition_pos`/`precondition_neg`,
`precondition_connective` (`'and'`/`'or'`, #13), `effect_pos`/`effect_neg`,
and the numeric `precondition_num`/`effect_num` (#11) — summarise the
unconditional conjunctive part of an action and remain the fast path for plain
STRIPS domains.

**ADL (#10).** For full boolean / quantified / equality preconditions and
conditional / universal effects, an `Operator` also carries structured trees:

- `precondition_tree` (lifted) and `precondition` (grounded) — a `Condition`
  tree of `Lit` / `Not` / `And` / `Or` / `Equality` / `NumericCond` /
  `Exists` / `Forall`. `condition.holds(atoms, fluents)` evaluates the whole
  tree, so `or`, `imply`, `=` and quantifiers are **evaluated**, not merely
  preserved. `State.applicable` uses the grounded tree when present.
- `effect_tree` (lifted) and `conditional_effects` (grounded) — an `Effect`
  tree (`AddDel` / `NumEff` / `EffAnd` / `When` / `Universal`). Grounding
  compiles it into the unconditional `effect_pos`/`effect_neg`/`effect_num`
  plus a list of `CondEffect` guards that `State.apply` fires only when their
  condition holds in the pre-state.

Quantifiers are grounded by **expansion over the world objects**:
`(forall (?x - t) φ)` becomes the `And` of `φ` instantiated for every object of
type `t` (vacuously *true* when there are none), and `(exists …)` the
corresponding `Or` (vacuously *false*). The `simple_conjunction` flag records
whether the precondition is a plain conjunction of literals/numerics; anything
richer makes the grounder fall back from static pruning to the full cartesian
product so no applicable binding is dropped.

### Numeric fluents (#11)
`Expr` tree — `Num`, `Fluent`, `BinOp`, `Neg` — each with
`ground(varvals)` and `value(valuation)`. `NumericConstraint.holds(valuation)`
evaluates a numeric precondition; `NumericEffect.apply(valuation)` returns the
`(head, new_value)` an effect produces.

### `DurativeAction` (#23)
A durative action with time-tagged `condition_pos`/`condition_neg` keyed by
`'start'`/`'over'`/`'end'`, `effect_pos`/`effect_neg` keyed by
`'start'`/`'end'`, and a `duration`. Recovered into the model; the reference
planners are non-temporal, but the `temporal` planner (below) schedules them.

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

### Durative surface (#23)

The semantic layer on top of `DurativeAction` — validation and `at start`
applicability, deliberately short of a temporal planner:

- **`validate_durative_action(action, declared_predicates=None)`** — raises
  `DurativeValidationError` unless the duration is present and strictly
  positive, every `?variable` in a condition/effect is a declared parameter,
  and (when `declared_predicates` is passed, e.g. `dp.predicates()`) every
  referenced predicate is declared.
- **`validate_durative_actions(dp)`** — validates every durative action in a
  `DomainProblem` against its declared predicates; no-op without durative
  actions.
- **`DurativeState`** — small immutable set of ground atoms
  (`DurativeState.from_problem(dp)`). `state.applicable(action)` checks only
  the grounded action's **`at start`** conditions, mirroring
  `State.applicable(op)`. No numeric valuation, no timeline: `over all` /
  `at end` are not evaluated, and durative *solving* stays out of scope.

```python
from pddlpy import DomainProblem
from pddlpy.planning import DurativeState, validate_durative_actions

dp = DomainProblem("domain.pddl", "problem.pddl")
validate_durative_actions(dp)
state = DurativeState.from_problem(dp)
startable = [a for name in dp.durative_operators()
             for a in dp.ground_durative_operator(name)
             if state.applicable(a)]
```

```python
from pddlpy import DomainProblem
from pddlpy.planning import get

dp = DomainProblem("domain.pddl", "problem.pddl")
plan = get("astar").solve(dp)
print(plan.cost, plan.action_names())
```

### Temporal planner (#84)

The `temporal` planner *solves* durative-action domains, enforcing the full
time-tagged contract that `DurativeState` (at-start only) cannot. It declares
the `:durative-actions` capability and returns a `TemporalPlan`.

- **`apply_durative(state, action)`** — applies one grounded `DurativeAction`
  under **sequential** semantics: it checks `at start` in `state`, applies the
  start effects, then checks the `over all` invariant and the `at end`
  conditions against that mid-state (with no concurrency it persists for the
  whole duration), and finally applies the end effects at `start + duration`.
  Returns the successor `State`, or `None` if any condition fails.
- **`TemporalPlanner`** (`get("temporal")`) — uniform-cost search over
  accumulated duration; instantaneous actions participate as zero-duration
  steps, so mixed domains work. Returns a makespan-minimal sequential schedule.
- **`TemporalPlan`** — a `Plan` whose `steps` are `ScheduledAction`s
  (`action`, `start`, `duration`, `end`); its `makespan` doubles as the plan
  `cost`.

```python
from pddlpy import DomainProblem
from pddlpy.planning import get

dp = DomainProblem("durative-domain.pddl", "durative-problem.pddl")
plan = get("temporal").solve(dp)
if plan is not None:
    print("makespan", plan.makespan)
    for step in plan.steps:
        print(step.start, step.action.operator_name, step.duration)
```

Because semantics are sequential (v1), actions never overlap: `over all` and
`at end` are constrained only by the action's own start effects. **Required
concurrency** (actions that must overlap, e.g. match/cellar) is out of scope —
a follow-up to this planner.

## Known limitations

- **Union types:** the `:types` hierarchy is supported (#22) — a parameter
  typed with a supertype binds objects of any transitive subtype — but
  `(either ...)` union types are not handled.
- **ADL (#10):** conditional/universal effects, quantified and full-boolean
  preconditions and `=` equality are parsed, grounded and **solved** by the
  reference planners. One gap remains: ADL structure on the **goal** side of a
  problem (`or`/`forall`/`exists` in `(:goal …)`) is still flattened to a
  conjunction of atoms.
- **Durative actions:** solved sequentially by the `temporal` planner (#84);
  the reference STRIPS planners remain non-temporal. **Required concurrency**
  (mandatory action overlap) and PDDL+ processes/events are out of scope.
