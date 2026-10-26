# Changelog

All notable changes to `pddlpy` are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **No runtime dependencies** (#148): the ANTLR runtime (4.13.2, BSD-3-Clause)
  is vendored in `pddlpy/_vendor/antlr4`, and `antlr4-python3-runtime` is no
  longer a dependency. The runtime pin had to be exact, so `pddlpy` could not
  be installed next to packages pinning another version, such as
  omegaconf/Hydra (`4.9.*`).
- **No Java needed to run the tests**: the generated parser files are now
  committed. Java is needed only to change `pddl.g4`, and CI checks that the
  committed parser matches the grammar.

### Fixed
- **`validate` missed undeclared requirements** (#144): `diagnose()` (the
  `validate` CLI command and MCP tool) now runs the declared-vs-used
  `:requirements` check that `solve` runs, and reports a `requirements` error.
  Before, `validate` could report `valid: true` for a pair that `solve` then
  refused with `UnsupportedRequirementsError`.
- **License metadata**: package metadata wrongly declared MIT (`License: MIT`
  and the MIT classifier) in every release up to and including 1.2.2. The
  project has always been Apache-2.0, as `LICENSE.txt` and the source headers
  state. Metadata now uses PEP 639 (`License-Expression: Apache-2.0`) and
  bundles `LICENSE.txt`.
- **Wheel installed stray files into `site-packages`**: `LICENSE.txt`,
  `README.md` and `pyproject.toml` were packed at the wheel root. They now
  ship only in the sdist; the license stays in the wheel's `.dist-info`.

## [1.2.2] - 2026-10-25

Maintenance release.

### Fixed
- **`pddlpy-mcp` crashed on install with `mcp` 2.x**: the `mcp` extra was
  unbounded (`>=1.2`), so fresh installs resolved `mcp` 2.x, which renamed
  `FastMCP` and fails at import. The extra is now capped at `mcp<2`.

### Changed
- **`mcp` extra floor raised to `>=1.30`**: `pddlpy[mcp]` no longer resolves
  to an `mcp` release affected by the StreamableHTTP session-accumulation
  advisory (fixed in 1.30.0). `pddlpy-mcp` serves over stdio and was not
  exposed; the floor keeps installs off the vulnerable versions.
- **MCP tool descriptions**: `ground` and `solve` document the unknown-operator
  error, the `temporal` and `ucs` planners, and unsupported-requirement
  failures, so MCP clients see the full tool contract.
- Declared the Python 3.13 classifier; CI now tests Python 3.11, 3.12 and 3.13.

## [1.2.1] - 2026-07-14

Patch release found in the v1.2.0 post-release check.

### Fixed
- **CLI/MCP temporal output** (#119): `pddlpy solve --planner temporal` and
  the MCP `solve` tool now render the `TemporalPlan` schedule — each step
  carries `start`, `duration` and `end`, and the result a top-level
  `makespan` (the generic `cost` is kept for compatibility). Previously the
  JSON showed only `{action, args}` per step and the schedule was lost.

### Quality
- 234 tests, 100% line coverage maintained.

## [1.2.0] - 2026-07-13

The planning release: durative actions are *solved* and the expressiveness
climbs from STRIPS to ADL.

### Added
- **ADL support** (#10): conditional effects (`when`), universal effects,
  quantified (`forall`/`exists`) and full-boolean (`and`/`or`/`not`/`imply`)
  preconditions, and `=` equality — parsed into Condition/Effect trees,
  grounded (quantifiers expand over typed world objects), and **evaluated by
  the reference planners** via capability negotiation (`:adl` and its
  sub-requirements). Plain STRIPS keeps its static-pruned fast path. Remaining
  gap (documented): ADL structure inside `(:goal ...)` is still flattened.
- **Temporal planner** (#84): `get("temporal")` *solves* durative-action
  domains. It enforces the full time-tagged contract — `at start`, `over all`
  (invariant across the duration), and `at end` — applying start effects at the
  start point and end effects at start+duration, under **sequential** semantics
  (actions never overlap; instantaneous actions participate as zero-duration
  steps). Returns a `TemporalPlan` whose `ScheduledAction` steps carry start
  times and durations and whose `makespan` is the plan cost. Registered with
  the `:durative-actions` capability. Required concurrency (mandatory overlap)
  remains out of scope.
- **Real LLM transcript in the docs** (#99, #106): `docs/llm-interaction.md`
  now walks through a captured qwen-2.5-72b conversation (write PDDL →
  `validate` → recover from a real `solve` rejection → narrate the `ucs`
  optimum), backed by the manual end-to-end harness in `e2e/llm/` with an
  automated soundness gate and observed-results notes for small models.

### Quality
- 232 tests, 100% line coverage maintained.

## [1.1.2] - 2026-07-12

Infrastructure release — no library changes.

### Changed
- **Publishing moved entirely to GitHub Actions** (#96): pushing a `v*` tag
  builds and uploads to TestPyPI then PyPI via [Trusted
  Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC — no stored
  credentials). The local `make pypitest`/`make pypipublish` targets and the
  `twine`/`build` dev dependencies were removed; this is the first release
  published by the pipeline itself.
- **CI on every PR**: grammar + tests, a 100%-coverage gate, ruff, mypy.

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

[1.2.2]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.2.2
[1.2.1]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.2.1
[1.2.0]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.2.0
[1.1.2]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.1.2
[1.1.1]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.1.1
[1.1.0]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.1.0
[1.0.0]: https://github.com/hfoffani/pddl-lib/releases/tag/v1.0.0
