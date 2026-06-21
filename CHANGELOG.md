# Changelog

All notable changes to `pddlpy` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-06-21

First stable release. The library grew from a STRIPS parser into a parser +
object model + a small, strictly-layered reference planning layer, with a stable
public API (`Development Status :: 5 - Production/Stable`).

### Added
- **Planning layer** (`pddlpy.planning`): immutable `State` / `Plan`, `GroundedTask`,
  a `Planner` ABC + `registry`, and four reference planners — `bfs`, `astar`,
  `gbfs`, `ucs` (#1).
- **Capability negotiation**: planners declare supported `:requirements` and fail
  fast with `UnsupportedRequirementsError` on unsupported domains; `:requirements`
  enforcement against used features (#9).
- **Numeric fluents**: `:functions`, numeric preconditions/effects, and a numeric
  valuation carried by `State` (#11).
- **Action costs**: `total-cost`, `(:metric ...)`, `Plan.cost`, and cost-optimal
  `UniformCostPlanner` (#3).
- **Type hierarchies**: multi-level `:types` captured (`types()` / `subtypes_of()`);
  a supertype parameter binds objects of any transitive subtype (#22).
- **Pluggable variable binding**: `StaticPrunedBinder` (default) and `CartesianBinder`
  (#12).
- **Durative actions**: parsed and grounded into a `DurativeAction` model
  (time-tagged `at start` / `over all` / `at end`), plus `DurativeState` `at start`
  applicability and `validate_durative_action[s]` (#23). Temporal *solving* is out of
  scope (tracked in #84).
- **`DomainProblem.predicates()`** accessor.
- **Example showcase** (`examples/`) and a README chapter; `make examples`.

### Changed
- PDDL keywords are now **case-insensitive**, so standard IPC files parse (#20, #36).
- `Atom`/tuple state comparison resolved via the new `State` type — applicability and
  goal checks no longer need manual casting (#21).

### Fixed
- Trailing line comment without a final newline no longer breaks parsing (#19).
- Grounding is keyed per operator; grounding one operator no longer reuses another's
  bindings (#26).
- Disjunctive (`or`) preconditions are no longer silently flattened to `and`; the
  top-level connective is preserved (#13).
- Removed a Python-2-only import path (#16).

### Quality
- 150 tests, 100% line coverage; layering between grammar / model / planner enforced
  by a test. Python 3.11+.

[1.0.0]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.0.0
