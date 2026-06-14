# TODO

Ordered to match the PRD roadmap: **Phase 0 (foundation) gates everything else.** Issue
numbers link to GitHub. Do not start a later phase until the prior phase's tests are green
(or its failures are documented as xfail).

---

## Phase 0 — Foundation: correctness + coverage  *(gating)*

### Test & verification infrastructure (do first — it's the safety net for the fixes below)
- [x] **Stand up coverage tooling** — add `pytest` + `coverage`/`pytest-cov`, wire into the
      Makefile (`make coverage`), establish and print the baseline % for `pddlpy/pddl.py`.
      *Baseline: 83% for `pddlpy/pddl.py`.*
- [x] **Add a benchmark parse-corpus** — vendored canonical PDDL files (IPC blocksworld,
      gripper, logistics) that MUST parse; the #36 regression guard.
      *`tests/corpus/` + `tests/test_corpus.py` (9 tests).*
- [x] **Fix `make testgrammar` Java classpath** — currently fails; Java can't find the ANTLR4
      runtime. Add `antlr-4.13.2-complete.jar` to the classpath so grammar changes stay verifiable.
      *Used absolute jar path (`$(CURDIR)`) so it survives `cd tmp`; added `.` to GRUN classpath.*
- [ ] **Drive line coverage toward 100%** — write tests covering every line of `pddl.py`.
      Coverage is used here as a **bug-finder**: where a line can't be made to pass, mark the
      test `xfail` with the owning issue number. Failing tests are EXPECTED and document
      known/undiscovered bugs — do not delete or weaken them to go green.

### Parser & object-model bug fixes (each lands with a regression test)
- [ ] **#20 / #36 — keyword case-insensitivity** — `(:INIT ...)` and other uppercase keywords
      in standard IPC files are not recognized; `initialstate()` returns empty with no error.
      Make grammar keywords case-insensitive. *Confirmed reproducible on IPC blocksworld.*
      **Highest impact: unblocks parsing of real-world files.**
- [ ] **#26 — grounding cross-operator cache bug** — `vargroundspace` cached per first operator;
      grounding a second operator reuses the first's bindings. Key the cache correctly per
      operator's own variable types.
- [ ] **#13 — OR preconditions silently flattened to AND** — at minimum **preserve the
      connective** so `or` is distinguishable from `and` and no longer silently mis-modeled.
      Full and/or/not tree + DNF evaluation is deferred to keep the phase short (see #10).
- [ ] **#19 — comment on last line breaks parsing** — adopt the suggested `LINE_COMMENT` rule
      that accepts `EOF` as a terminator.

### Triage / investigation (Phase 0 scope)
- [ ] **#27 — user-supplied files fail to parse** — reproduce; likely a duplicate of #20/#23
      (file uses `:durative-actions`). Confirm and link or fix.
- [ ] **#16 — `No module named '__builtin__'`** — Python 2 leftover; confirm it's gone on 3.11+
      and close, or remove the offending import.
- [ ] **#18 — `InvalidCastException` reading types** (.NET port) — confirm scope; the .NET/DLL
      path may be out of scope for this Python repo → decide & label.

---

## Phase 1 — Planner interface + reference planner (STRIPS)  *(addresses #1)*
- [ ] **Define `Planner` ABC + `Plan` / `State` types** (PRD §5).
- [ ] **#21 — type mismatch `initialstate()` vs `precondition_pos`** — `Atom` vs tuple makes
      `issubset` always false. Resolve via the new `State` type so `operator.applicable(state)`
      works without manual casting. Linchpin: same change is both the bug fix and the planner's
      core data structure.
- [ ] **Factor out grounding + successor generation** as shared components below the planner.
- [ ] **Implement a blind-search reference planner** — BFS first, then A* / GBFS.
- [ ] **Capability metadata + registry** (PRD §7); fail fast on unsupported `:requirements`.
- [ ] **#9 — enforce `:requirements`** — validate domain feature use against declared requirements.
- [ ] **Boundary enforcement test** — planner imports nothing from grammar; model imports no
      planner code (import-linter rule or test).
- [ ] **#2 — API docs** — document the planner + model API (or defer per Open Question §9).

## Phase 2 — Numeric fluents  *(#11)*
- [ ] Parse `:functions`, numeric preconditions, numeric effects.
- [ ] Object model: effect expressions; extend successor generation to evaluate them.

## Phase 3 — Action costs
- [ ] `total-cost` handling; `Plan` carries cost.
- [ ] Cost-aware search in the reference planner.

## Phase 4 — Durative actions  *(#23)*
- [ ] **Complete duration-tag recovery** — grammar parses durative actions but Python recovery
      is incomplete (the known issue in CLAUDE.md).
- [ ] **`DurativeAction` type** — time-tagged conditions/effects (`at start / over all / at end`).
- [ ] Decide temporal state representation; temporal-capable planner (or document non-coverage).

---

## Backlog / decisions
- [ ] **#10 — ADL** (conditional effects, quantifiers) — schedule after #13's precondition tree.
- [ ] **#12 — better variable binding** — revisit once grounding (#26) is fixed; may be subsumed.
- [ ] **#22 — type super-sets** — typing hierarchy enhancement; Phase 2-ish.
- [ ] **#35 — HDDL parser** — decided **out of scope** (PRD §4). Reply and close.

## Done / merged
- [x] **Merge `ai-setup` branch** — CLAUDE.md setup (merged, #60).

---

*Last updated: 2026-06-14*
