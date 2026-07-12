# Changelog

All notable changes to `pddlpy` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-07-12

### Fixed
- **UTF-8 PDDL files parse** (#103): ANTLR's `FileStream` defaults to ASCII,
  so any non-ASCII byte — even in a comment like `; camión` — raised
  `UnicodeDecodeError` before parsing started. Files are now read as UTF-8
  (a strict ASCII superset; existing files parse unchanged).

### Added
- **LLM ↔ pddlpy worked example** (#99): `docs/llm-interaction.md` — natural
  language → PDDL → `pddlpy solve` → natural language, on a small cost-optimal
  routing problem where the intuitive answer is wrong; courier example PDDL
  under `examples/pddl/`, linked from the README with LLM+P / PlanBench
  references. The `run-pddlpy` dev skill is hidden from public skills
  discovery (`metadata.internal`).

### Quality
- 191 tests, 100% line coverage maintained.

## [1.1.0] - 2026-07-12

The "standalone tool" release: pddlpy is now drivable from the shell, by MCP
clients, and by coding agents — not only as a Python library.

### Added
- **CLI** (#85): a `pddlpy` console command with JSON output —
  `pddlpy parse|ground|solve|validate DOMAIN PROBLEM`. `solve` takes
  `--planner` (`bfs`/`astar`/`gbfs`/`ucs`, default `astar`). Exit codes:
  `0` success, `1` no plan found / validation issues, `2` bad input.
  Zero-install via `uvx pddlpy ...`.
- **MCP server** (#86): `pddlpy-mcp` (stdio) exposing `parse`, `ground`,
  `solve` and `validate` as Model Context Protocol tools with structured
  JSON results. The `mcp` SDK is an optional extra: `pip install "pddlpy[mcp]"`.
- **`validate` diagnostics** (#94): `pddlpy.diagnostics.diagnose()` bundles
  collected ANTLR syntax errors, atoms over undeclared predicates, ground
  atoms naming unknown objects, operators grounding to zero instances
  (warning), and durative-action validation — the feedback step for agentic
  natural-language → PDDL translation loops.
- **`pddlpy.serialize`**: JSON-friendly dict renderings of `DomainProblem`,
  grounded `Operator` and `Plan`, shared by the CLI and the MCP server.
- **Agent Skill**: `skills/pddlpy/SKILL.md` reworked for standalone use
  (installable via `npx skills add hfoffani/pddl-lib`), documenting the CLI
  fast path and the write → validate → fix → solve loop.

### Fixed
- `worldobjects()` no longer includes predicate names as objects in untyped
  domains, which inflated grounding (e.g. blocksworld `pick-up` grounded to
  8 instances instead of 3) (#96).

### Quality
- 187 tests, 100% line coverage maintained.

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

[1.1.1]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.1.1
[1.1.0]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.1.0
[1.0.0]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.0.0
