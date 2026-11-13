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
  files with syntax errors, and durative actions with numeric, conditional or quantified parts
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
| `:fluents`, `:numeric-fluents` | 2.1, 3.1 | yes | bfs, astar, gbfs, ucs | yes, except on durative actions | Numeric preconditions and `assign` / `increase` / `decrease` / `scale-up` / `scale-down` effects. Numeric goals are supported ([#138]). temporal applies numeric conditions and effects on instantaneous actions only; it refuses durative actions with numeric parts ([#139]). |
| `:durative-actions` | 2.1 | yes | temporal | yes, overlapping actions included | Sequential semantics only: actions never overlap, so domains that need concurrency are not solved. The duration must be a number, e.g. `(= ?duration 4)`; `(= ?duration (f))` is rejected. temporal refuses durative actions with numeric, conditional or quantified parts ([#139]). Not combinable with the ADL requirements (temporal refuses those). |
| `:duration-inequalities` | 2.1 | partly | none | no | Parses, declared or not. An inequality bound is not taken as a duration: `validate` reports the action, and `temporal` and `validate-plan` refuse it ([#143]). |
| `:continuous-effects` | 2.1 | no | none | no | The key is recognized, and `solve`, `validate-plan` and `validate` refuse it as not supported yet ([#208]). `#t` is not recognized (syntax error). |
| `:derived-predicates` | 2.2 | yes | bfs, astar, gbfs, ucs | yes | `(:derived (p ?x) GD)` rules (`dp.domain.derived`) are recomputed in every state: recursive rules to a fixpoint, negated derived predicates by strata ([#141]). Rules that are not stratifiable are refused, and so are recursive rules that compare numeric fluents (VAL's verdict on those depends on where the recursion starts). temporal refuses derived predicates. Slow on large problems: every state re-evaluates every grounded rule. |
| `:timed-initial-literals` | 2.2 | yes | temporal | yes | `(at 5 (p))` in `:init` is kept out of `initialstate()` and stored with its time in `dp.problem.timed_literals` ([#142]). temporal can wait for a literal or delay an action so it ends just after one, applies the ones that happen during an action to its `over all` conditions, treats literals that add and delete one atom at the same time as unsolvable (`validate` reports them), keeps every step start and end at least 0.001 away from a literal, and judges the goal after the last literal, as VAL does. Its schedules are not always makespan-minimal with literals. The classical planners refuse them. |
| `:preferences` | 3.0 | partly | ucs | yes (they never make a plan invalid) | Goal preferences, `(preference name GD)` also under `and` / `forall`, are kept apart from the hard goal (`dp.problem.preferences`; `goals()` lists hard atoms only), and `(is-violated name)` parses in `:metric` ([#201]). `ucs` minimizes a metric linear in `(total-cost)` and `(is-violated ...)` with non-negative weights (`maximize` negates it); a quantified preference counts each violated instance. Other metric shapes are refused, and so is a metric without `(total-cost)` when a condition reads it (the search could not end). The other planners refuse preferences. Preferences in `:action` preconditions do not parse (in durative-action conditions they parse and are ignored). |
| `:constraints` | 3.0 | partly | none | no | Declaring the key is a syntax error ([#140]). A `(:constraints ...)` block in the domain or problem loads but is not modeled: `solve` and `validate-plan` refuse it, and `validate` reports an `unsupported` error. |
| `:action-costs` | 3.1 | yes | ucs (cost-optimal); bfs, astar, gbfs, temporal | yes | `(increase (total-cost) ...)` and `(:metric minimize (total-cost))`. Every planner reports `Plan.cost`, but only ucs minimizes it. temporal minimizes makespan, and `(:metric minimize (total-time))` parses ([#158]). |
| `:object-fluents` | 3.1 | no | none | no | The key is recognized, and `solve`, `validate-plan` and `validate` refuse it as not supported yet ([#208]). Object-valued functions do not parse. |
| `:domain-axioms`, `:subgoals-through-axioms`, `:safety-constraints`, `:expression-evaluation`, `:open-world`, `:true-negation`, `:ucpop` | 1.2 | key only | none | no | Obsolete. The keys are recognized, and `solve`, `validate-plan` and `validate` refuse them by name ([#208]). |

**Goals.** Any goal description is supported: `and`, `not`, `or`, `imply`,
`exists`, `forall`, `=` and numeric comparisons ([#138]), whatever the
domain declares in `:requirements`. With a goal other than a conjunction of
atoms, `astar` and `gbfs` fall back to a blind heuristic (0 at a goal, else
1).

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
[#201]: https://github.com/hfoffani/pddl-lib/issues/201
[#142]: https://github.com/hfoffani/pddl-lib/issues/142
[#143]: https://github.com/hfoffani/pddl-lib/issues/143
[#144]: https://github.com/hfoffani/pddl-lib/issues/144
[#208]: https://github.com/hfoffani/pddl-lib/issues/208
