# TODO — Road to 1.0

Live status for the 1.0 release (see `PRD.md` for the detailed spec). Temporary file.

**Snapshot:** **1.0.0 shipped** — live on PyPI, tagged `v1.0.0`, CHANGELOG added.
150 tests, **100% coverage**. Only leftover: the `docs/object-model.md` durative note.

---

## 1.0 — must ship

### #23 — Durative actions: validation + applicability (the "middle" slice)
- [x] **Validation** — duration well-formed & positive; time-tagged conditions/effects
      reference declared predicates/parameters; clear error otherwise.
      *`validate_durative_action` / `validate_durative_actions` + `DurativeValidationError`;
      `DomainProblem.predicates()` accessor added.*
- [x] **Applicability** — check a grounded `DurativeAction`'s **`at start`** conditions against
      a state, mirroring `State.applicable(operator)`. `over all`/`at end` not evaluated in 1.0.
      **No scheduler, no temporal planner.** *`DurativeState.applicable`.*
- [x] **Surface:** small dedicated **`DurativeState`** type in `pddlpy.planning`; keep layering
      clean (imports object model, never the grammar). *`pddlpy/planning/durative.py`.*
- [x] **Tests** — add validation/applicability tests; **remove stale `xfail`/"Phase 4" markers**.
      *`tests/test_durative_state.py` (16 tests, 100% cover of `durative.py`); cleaned the stale
      triage docstring. No `@xfail` markers remained.*
- [x] Keep documenting that durative *solving* (temporal planning) is out of scope.
      *README durative section + example showcase table both state "not temporally solved".*

### #80 — More examples + README chapter
- [x] Example: parsing basics (core object model) — *`examples/01_parsing_basics.py`*
- [x] Example: types / type hierarchies — *`examples/02_type_hierarchy.py`*
- [x] Example: logical operators (and/or/not preconditions) — *`examples/03_logical_operators.py`*
- [x] Example: planners (bfs/astar + registry) — *`examples/04_planners.py`*
- [x] Example: numeric fluents + action costs — *`examples/05_numeric_and_costs.py`*
- [x] Example: durative actions (model + applicability; not solved) — *`examples/06_durative.py`*
- [x] README chapter with a table linking each example, increasing complexity
- [x] Self-contained PDDL under `examples/pddl/`; `make examples` target; smoke test
      (`tests/test_examples.py`) runs every example. *Suite 150 passing, 100% coverage.*
- [ ] ("running as a tool" / "LLM interface" examples — **deferred** post-1.0 with the thin CLI)

### #81 — Release v1.0 to PyPI — **done** (PR #87, closed)
- [x] Bump `pyproject.toml` → `1.0.0`; set `Development Status` classifier to `5 - Production/Stable`
- [x] QA: `make` green, coverage 100%, build wheel/sdist, smoke-test the wheel
- [x] Publish TestPyPI (`make pypitest`) → verify install → PyPI (`make pypipublish`).
      *1.0.0 is the latest release on PyPI.*
- [x] Tag release + short changelog since 0.4.x. *Tag `v1.0.0`; `CHANGELOG.md` added.*

### Issue triage (clean slate for 1.0)
- [x] Verify against current code, then **close**: #36, #16, #19, #21, #26, #27 (dup of #23).
      *All verified fixed on `main` and now closed.*
- [x] Scope to **milestone**: #10 → 2.0, #35 → 3.0. *Milestones 2.0 (#5) / 3.0 (#6) created;
      #10 and #35 assigned with explanatory comments.*

### Docs
- [x] Update `README.md` as durative applicability + examples land (current capabilities only).
      *Durative section, example showcase table, `DurativeState` mentioned.*
- [ ] Update `docs/object-model.md` for the durative applicability surface
      (*`DurativeState` / `validate_durative_action` not yet documented there*)

---

## 2.0 — ADL (#10) — out of scope for 1.0
- [ ] Conditional effects (`when`)
- [ ] Quantifiers (`forall` / `exists`) in conditions
- [ ] Full and/or/not precondition tree (beyond the current connective handling)

## 3.0 / future — HDDL (#35) — out of scope
- [ ] HTN / HDDL parser — separate formalism; decide as a distinct effort

## Future (no milestone)
- [ ] Temporal planner that *solves* durative-action domains
- [ ] Heuristic improvements for the reference planners

---

## Done (recent, verified)
- [x] Case-insensitive keywords → standard IPC files parse (#36)
- [x] `:requirements` capture + capability negotiation (#9)
- [x] Planner interface + registry + bfs/astar/gbfs/ucs
- [x] Numeric fluents (#11), action costs (#3)
- [x] Type hierarchy (#22), pluggable variable binding (#12)
- [x] Durative parsing + `DurativeAction` model + grounding (#23 parsing half)
- [x] Precondition connectives (#13), strict layering, **100% coverage**

---

*Last updated: 2026-07-12*
