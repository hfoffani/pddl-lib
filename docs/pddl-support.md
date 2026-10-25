# Supported :requirements

This is the state of the code today, checked against the parser and the
planners, not a wish list.

* **Parse**: the grammar accepts it and the object model captures it.
  `validate` runs its checks on everything that parses.
* **Solve**: the planners that accept the requirement and handle it.
  A planner refuses a domain that declares a requirement it does not support
  (`UnsupportedRequirementsError`, CLI exit `2`). `gbfs` accepts the same set
  as `astar`.

| Requirement | PDDL | Parse | Solve | Notes |
|---|---|---|---|---|
| `:strips` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | |
| `:typing` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | Multi-level hierarchies; a supertype parameter binds every transitive subtype. `(either ...)` parses but binds no objects (`validate` reports zero groundings). |
| `:negative-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | Preconditions only, see goals below. |
| `:disjunctive-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | Preconditions only. temporal refuses it. |
| `:equality` | 1.2 | yes | bfs, astar, gbfs, ucs, temporal | |
| `:existential-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | temporal refuses it. |
| `:universal-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | temporal refuses it. |
| `:quantified-preconditions` | 1.2 | yes | bfs, astar, gbfs, ucs | temporal refuses it. |
| `:conditional-effects` | 1.2 | yes | bfs, astar, gbfs, ucs | `when` and `forall` effects. temporal refuses it. |
| `:adl` | 1.2 | yes | bfs, astar, gbfs, ucs | Covers the rows above. temporal refuses it. |
| `:fluents`, `:numeric-fluents` | 2.1, 3.1 | yes | bfs, astar, gbfs, ucs | Numeric preconditions and `assign` / `increase` / `decrease` / `scale-up` / `scale-down` effects. Numeric goals are dropped ([#138]). temporal accepts the requirement but only applies numeric conditions and effects on instantaneous actions; on durative actions it ignores them ([#139]). |
| `:durative-actions` | 2.1 | yes | temporal | Sequential semantics only: actions never overlap, so domains that need concurrency are not solved. The duration must be a number, e.g. `(= ?duration 4)`; `(= ?duration (f))` is rejected. Not combinable with the ADL requirements (temporal refuses those). |
| `:duration-inequalities` | 2.1 | no | none | Declaring it is a syntax error. Without the key, `(and (>= ?duration 1) (<= ?duration 3))` parses, but the last bound becomes a fixed duration ([#143]). |
| `:continuous-effects` | 2.1 | no | none | The key and `#t` are not recognized (syntax error). |
| `:derived-predicates` | 2.2 | no | none | The key is recognized, but `(:derived ...)` blocks do not parse ([#141]). |
| `:timed-initial-literals` | 2.2 | wrong | none | `(at 5 (p))` in `:init` parses, but the literal goes into the initial state as true at time 0. Every planner refuses the key; if a domain omits it, plans can be wrong ([#142]). |
| `:preferences` | 3.0 | no | none | The key is recognized; `preference` in goals or `:action` preconditions does not parse (it does parse inside durative-action conditions, and is ignored there). Planners refuse the key. |
| `:constraints` | 3.0 | no | none | Declaring the key is a syntax error, and a `(:constraints ...)` block in the domain or problem crashes the loader ([#140]). |
| `:action-costs` | 3.1 | yes | ucs (cost-optimal); bfs, astar, gbfs, temporal | `(increase (total-cost) ...)` and `(:metric minimize (total-cost))`. Every planner reports `Plan.cost`, but only ucs minimizes it. temporal minimizes makespan. |
| `:object-fluents` | 3.1 | no | none | Not recognized (syntax error). |
| `:domain-axioms`, `:subgoals-through-axioms`, `:safety-constraints`, `:expression-evaluation`, `:open-world`, `:true-negation`, `:ucpop` | 1.2 | no | none | Not recognized (syntax error). |

**Goals.** Every planner reads `(:goal ...)` as a conjunction of positive
atoms. Other goal forms parse without an error but are misread: `(not (p))`
becomes the goal `(p)`, `or` is treated as `and`, the body of `exists` /
`forall` is kept with its variables unbound, and numeric comparisons are
dropped. `validate` only catches the `exists` / `forall` case, as an unknown
object `?x` ([#138]). Goal-side ADL is first in the requirements part of the
[roadmap](../README.md#roadmap).

**Declared vs. used.** When a domain declares any `:requirements`, `solve`
also checks that the features it uses (typing, negation, disjunction,
equality, quantifiers, conditional effects) are declared, and refuses the
domain otherwise. Domains with no `:requirements` at all are accepted as they
are. `validate` does not run this check yet ([#144]).

[#138]: https://github.com/hfoffani/pddl-lib/issues/138
[#139]: https://github.com/hfoffani/pddl-lib/issues/139
[#140]: https://github.com/hfoffani/pddl-lib/issues/140
[#141]: https://github.com/hfoffani/pddl-lib/issues/141
[#142]: https://github.com/hfoffani/pddl-lib/issues/142
[#143]: https://github.com/hfoffani/pddl-lib/issues/143
[#144]: https://github.com/hfoffani/pddl-lib/issues/144
