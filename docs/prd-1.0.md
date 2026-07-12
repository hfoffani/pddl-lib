# PRD: Road to pddlpy 1.0

> **Status:** Archived — 1.0.0 shipped to PyPI (tag `v1.0.0`). Kept as the historical
> design spec because code docstrings reference its sections (e.g. "PRD §5.4").
> **Owner:** Hernán
> Current capabilities live in `README.md`; future work is tracked in GitHub
> issues and milestones (2.0 ADL #10, 3.0 HDDL #35, CLI #85, LLM/MCP #86,
> temporal solving #84).

---

## 1. Where we actually are (verified on `main`)

The library is far more complete than a "parser only" tool. Verified present and tested:

- **Parser + object model:** STRIPS, typing **with multi-level hierarchy** (`types()`,
  `subtypes_of()`), pluggable variable binding (`StaticPrunedBinder`/`CartesianBinder`),
  `:requirements` capture, case-insensitive keywords (standard IPC files parse).
- **Precondition connectives** (and/or/not) handled — not silently flattened.
- **Numeric fluents** (`:functions`, numeric preconditions/effects).
- **Action costs** (`total-cost`, `:metric`), cost-optimal `ucs`.
- **Planning layer** (`pddlpy.planning`, strictly layered): `State`, `Plan`, `GroundedTask`,
  `Planner` ABC + `registry`, capability negotiation (`UnsupportedRequirementsError`), and
  four reference planners — `bfs`, `astar`, `gbfs`, `ucs`.
- **Durative actions:** parsed and **grounded** into a `DurativeAction` type with time-tagged
  conditions (`at start`/`over all`/`at end`) and effects, plus duration. Even the previously
  failing issue-#27 file now parses, grounds, and exposes its tags.
- **Quality:** 127 tests, **100% line coverage** (804 statements, 0 missed), layering enforced
  by `test_layering.py`.

**Implication:** the prior PRD's Phases 0–3 are shipped. 1.0 is a short, polish-and-release
effort, not a feature build-out.

## 2. Goal

Ship a credible, stable **1.0.0** to PyPI **soon**. "1.0" is a promise of a stable public API
and reliable behaviour for the subset we claim — it is **not** a promise of every PDDL feature.

## 3. Version horizon (agreed)

| Version | Theme | Tickets |
|---------|-------|---------|
| **1.0** | Finalize durative (validation/applicability), examples, docs, release | #23, #80, #81 |
| **2.0** | **ADL** — conditional effects (`when`), quantifiers (`forall`/`exists`), full and/or/not tree | #10 |
| **3.0 / future** | **HDDL** (HTN formalism) | #35 |
| Future | Temporal planner that *solves* durative-action domains | — |

ADL (#10) and HDDL (#35) are **out of scope for 1.0**. A temporal planner is out of scope
indefinitely (the reference planners are non-temporal by design).

---

## 4. 1.0 scope — what to do

### 4.1 Durative actions — complete the "middle" slice (#23)

Parsing, the `DurativeAction` object model, and grounding are **done**. For 1.0, add the
**semantic / applicability** layer — **no temporal scheduler, no temporal planner**:

- **Validation:** duration is well-formed and positive; time-tagged conditions/effects are
  consistent and reference declared predicates/parameters; raise a clear error otherwise.
- **Applicability:** given a state, check whether a grounded `DurativeAction`'s **`at start`**
  conditions hold — analogous to `State.applicable(operator)` for instantaneous actions, but
  **without** building a timeline or scheduling overlapping actions. For 1.0 we check **only
  `at start`**; `over all` / `at end` applicability is documented as not yet evaluated.
- **Surface:** a small dedicated **`DurativeState`** type in `pddlpy.planning`, mirroring the
  existing `State.applicable` / `State.apply` ergonomics, kept layering-clean (imports the
  object model, never the grammar).
- Remove the now-stale `xfail`/"incomplete, Phase 4" markers in `tests/test_triage.py` /
  `tests/test_durative.py`; add tests for the new validation/applicability.
- **Explicitly keep documenting** that durative *solving* (temporal planning) is out of scope.

### 4.2 More examples + README chapter (#80)

Add worked examples of increasing complexity for the capabilities users may not realise exist,
and a README chapter with a table linking each:

- Types / type hierarchies
- Planners (bfs/astar/gbfs/ucs, registry)
- Logical operators (and/or/not preconditions)
- Numeric fluents and action costs
- Durative actions (model + the new applicability check; note: not solved)

> `#80` also lists "running as a tool" and an "LLM interface." There is no CLI/tool or LLM
> surface today, and a thin CLI is **deferred to post-1.0** (decision §6), so those two
> examples are **deferred** as well. Keep 1.0 examples to capabilities that already exist.

### 4.3 Release engineering (#81)

- Bump `pyproject.toml` to `1.0.0`; set the `Development Status` classifier to
  `5 - Production/Stable` (one-line change).
- QA pass: `make` green, coverage still 100%, build wheel/sdist, smoke-test the wheel.
- Publish to TestPyPI (`make pypitest`), verify install, then PyPI (`make pypipublish`).
- Tag the release; short changelog of everything shipped since 0.4.x.

### 4.4 Issue triage for a clean 1.0

- **Close as fixed (with the covering test):** #36 (case-insensitive parse), #16 (py2 import
  gone), #19/#21/#26 (verify against current code, then close), #27 (dup of #23, now parses).
- **Label out of scope / milestone:** #10 → 2.0, #35 → 3.0/future.
- Confirm none of the above silently regressed before closing.

### 4.5 Docs

- Keep `README.md` describing **current** capabilities only (it already does); update it as
  4.1/4.2 land — never ahead of the code.
- `docs/object-model.md` updated for the durative applicability surface.

---

## 5. Out of scope for 1.0

- ADL conditional effects / quantifiers (#10 → 2.0).
- HDDL (#35 → 3.0/future).
- Temporal planning / scheduling for durative actions (future).
- Performance work / competing with Fast Downward / LAMA.

## 6. Resolved decisions

- **Durative applicability surface:** a small dedicated **`DurativeState`** type in
  `pddlpy.planning`.
- **`over all` / `at end`:** for 1.0, check **`at start` only**; document the rest as not yet
  evaluated.
- **Thin CLI in 1.0:** **deferred** to post-1.0 → the #80 "running as a tool" / "LLM interface"
  examples are deferred with it.
- **Stability classifier:** **`5 - Production/Stable`**.

(No open questions remain for 1.0.)

## 7. Acceptance criteria (1.0)

- Durative actions: grounded actions can be validated and checked for `at start` applicability
  via `DurativeState`; new tests pass; no stale `xfail` markers remain.
- README has an examples chapter/table; each linked example runs.
- `1.0.0` is installable from PyPI; `make` green; coverage 100%.
- #36/#16/#19/#21/#26/#27 closed; #10 and #35 labelled to their milestones.
