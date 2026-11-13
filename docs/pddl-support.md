# Supported :requirements

This is the state of the code today, checked against the parser and the
planners, not a wish list.

* **Parse**: the grammar accepts it and the object model captures it.
  `validate` runs its checks on everything that parses.
* **Solve**: the planners that accept the requirement and handle it.
  A planner refuses a domain that declares a requirement it does not support
  (`UnsupportedRequirementsError`, CLI exit `2`). `gbfs` accepts the same set
  as `astar`.
* **Validate plan**: `validate-plan` / `simulate` judge plans for it, with
  VAL's semantics (#166). Otherwise they refuse the plan
  (`PlanValidationError`, CLI exit `2`) rather than guess; they also refuse
  goals other than a conjunction of atoms ([#138]), files with syntax
  errors, and durative actions with numeric, conditional or quantified parts
  ([#139]) or duration inequalities ([#143]).

| Requirement | PDDL | Parse | Solve | Validate plan | Notes |
|---|---|---|---|---|---|
| `:strips` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | yes | |
| `:typing` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | yes | Multi-level hierarchies; a supertype parameter binds every transitive subtype. `(either t1 t2)` binds objects of any member type (#200). |
| `:negative-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | yes | Preconditions only, see goals below. |
| `:disjunctive-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | yes | Preconditions only. temporal refuses it. |
| `:equality` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | yes | |
| `:existential-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | yes | temporal refuses it. |
| `:universal-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | yes | temporal refuses it. |
| `:quantified-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | yes | temporal refuses it. |
| `:conditional-effects` | 1.2 | yes | bfs, astar, gbfs, ucs | yes | `when` and `forall` effects. temporal refuses it. |
| `:adl` | 1.2 | yes | bfs, astar, gbfs, ucs | yes | Covers the rows above. temporal refuses it. |
| `:fluents`, `:numeric-fluents` | 2.1, 3.1 | yes | bfs, astar, gbfs, ucs | yes, except on durative actions | Numeric preconditions and `assign` / `increase` / `decrease` / `scale-up` / `scale-down` effects. Numeric goals are refused ([#138]). temporal applies numeric conditions and effects on instantaneous actions only; it refuses durative actions with numeric parts ([#139]). |
| `:durative-actions` | 2.1 | yes | temporal | yes, overlapping actions included | Sequential semantics only: actions never overlap, so domains that need concurrency are not solved. The duration must be a number, e.g. `(= ?duration 4)`; `(= ?duration (f))` is rejected. temporal refuses durative actions with numeric, conditional or quantified parts ([#139]). Not combinable with the ADL requirements (temporal refuses those). |
| `:duration-inequalities` | 2.1 | partly | none | no | Parses, declared or not. An inequality bound is not taken as a duration: `validate` reports the action, and `temporal` and `validate-plan` refuse it ([#143]). |
| `:continuous-effects` | 2.1 | no | none | no | The key and `#t` are not recognized (syntax error). |
| `:derived-predicates` | 2.2 | partly | none | no | `(:derived (p ?x) GD)` parses (heads in `dp.domain.derived`) but is not modeled: `validate` reports an `unsupported` error, and `solve` and `validate-plan` refuse it, declared or not ([#141]). |
| `:timed-initial-literals` | 2.2 | yes | none | no | `(at 5 (p))` in `:init` is kept out of `initialstate()` and stored with its time in `dp.problem.timed_literals`. `solve` and `validate-plan` refuse it, and `validate` reports an `unsupported` error, even when the key is not declared ([#142]). |
| `:preferences` | 3.0 | no | none | no | The key is recognized; `preference` in goals or `:action` preconditions does not parse (it does parse inside durative-action conditions, and is ignored there). Planners refuse the key. |
| `:constraints` | 3.0 | partly | none | no | Declaring the key is a syntax error ([#140]). A `(:constraints ...)` block in the domain or problem loads but is not modeled: `solve` and `validate-plan` refuse it, and `validate` reports an `unsupported` error. |
| `:action-costs` | 3.1 | yes | ucs (cost-optimal); bfs, astar, gbfs, temporal | yes | `(increase (total-cost) ...)` and `(:metric minimize (total-cost))`. Every planner reports `Plan.cost`, but only ucs minimizes it. temporal minimizes makespan, and `(:metric minimize (total-time))` parses ([#158]). |
| `:object-fluents` | 3.1 | no | none | no | Not recognized (syntax error). |
| `:domain-axioms`, `:subgoals-through-axioms`, `:safety-constraints`, `:expression-evaluation`, `:open-world`, `:true-negation`, `:ucpop` | 1.2 | no | none | no | Not recognized (syntax error). |

**Goals.** Only a conjunction of positive atoms is supported. The model
misreads other goal forms (`not`, `or`, `imply`, `exists`, `forall`, numeric
comparisons), so `solve` and `validate-plan` refuse them (exit `2`) and
`validate` reports an `unsupported` error ([#138]). Goal-side ADL is first in the requirements part of the
[roadmap](../README.md#roadmap).

**Declared vs. used.** When a domain declares any `:requirements`, `solve`
also checks that the features it uses (typing, negation, disjunction,
equality, quantifiers, conditional effects) are declared, and refuses the
domain otherwise. Domains with no `:requirements` at all are accepted as they
are. `validate` does not run this check yet ([#144]).

[#158]: https://github.com/hfoffani/pddl-lib/issues/158
[#138]: https://github.com/hfoffani/pddl-lib/issues/138
[#139]: https://github.com/hfoffani/pddl-lib/issues/139
[#140]: https://github.com/hfoffani/pddl-lib/issues/140
[#141]: https://github.com/hfoffani/pddl-lib/issues/141
[#142]: https://github.com/hfoffani/pddl-lib/issues/142
[#143]: https://github.com/hfoffani/pddl-lib/issues/143
[#144]: https://github.com/hfoffani/pddl-lib/issues/144
