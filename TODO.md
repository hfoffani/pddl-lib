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
- [x] **Drive line coverage toward 100%** — write tests covering every line of `pddl.py`.
      Coverage is used here as a **bug-finder**: where a line can't be made to pass, mark the
      test `xfail` with the owning issue number. Failing tests are EXPECTED and document
      known/undiscovered bugs — do not delete or weaken them to go green.
      *`pddlpy/pddl.py` at **100%** (23 passed, 1 xfail for #27/#23). The `__main__` guard is
      `# pragma: no cover`; the legacy `pddlpy/test.py` scaffolding is omitted from coverage.*

### Parser & object-model bug fixes (each lands with a regression test)
- [x] **#20 / #36 — keyword case-insensitivity** — `(:INIT ...)` and other uppercase keywords
      in standard IPC files are not recognized; `initialstate()` returns empty with no error.
      Make grammar keywords case-insensitive. *Confirmed reproducible on IPC blocksworld.*
      **Highest impact: unblocks parsing of real-world files.**
      *Fixed via grammar `options { caseInsensitive = true; }`; identifiers keep their case.
      Regression test `test_uppercase_keywords_parse`.*
- [x] **#26 — grounding cross-operator cache bug** — `vargroundspace` cached per first operator;
      grounding a second operator reuses the first's bindings. Key the cache correctly per
      operator's own variable types. *Already keyed per operator name (`vargroundspace[opname]`);
      verified independent + order-independent grounding and locked in with `tests/test_grounding.py`.*
- [x] **#13 — OR preconditions silently flattened to AND** — at minimum **preserve the
      connective** so `or` is distinguishable from `and` and no longer silently mis-modeled.
      Full and/or/not tree + DNF evaluation is deferred to keep the phase short (see #10).
      *Added `Operator.precondition_connective` ('and'|'or'), propagated to grounded operators;
      tests in `tests/test_precondition_connective.py`.*
- [x] **#19 — comment on last line breaks parsing** — adopt the suggested `LINE_COMMENT` rule
      that accepts `EOF` as a terminator. *`('\r'? '\n' | EOF)`; regression test
      `test_trailing_comment_without_newline`.*

### Triage / investigation (Phase 0 scope)
- [x] **#27 — user-supplied files fail to parse** — reproduce; likely a duplicate of #20/#23
      (file uses `:durative-actions`). Confirm and link or fix. *Confirmed = #23: a
      durative-action file raises `IndexError` in `enterTypedVariableList` (no
      `enterDurativeActionDef` scope is pushed). Vendored fixture + `xfail` test
      (`test_durative_action_parses`); fix deferred to Phase 4.*
- [x] **#16 — `No module named '__builtin__'`** — Python 2 leftover; confirm it's gone on 3.11+
      and close, or remove the offending import. *No `__builtin__`/py2 leftovers anywhere in the
      repo; guarded by `test_no_python2_builtin_import`. Close.*
- [x] **#18 — `InvalidCastException` reading types** (.NET port) — confirm scope; the .NET/DLL
      path may be out of scope for this Python repo → decide & label. *No .NET/C#/DLL artifacts in
      this repo; out of scope for the Python library. Label out-of-scope and close.*

---

## Phase 1 — Planner interface + reference planner (STRIPS)  *(addresses #1)*
- [x] **Define `Planner` ABC + `Plan` / `State` types** (PRD §5). *`pddlpy/planning/`:
      `Planner` ABC (`solve(domainproblem) -> Plan | None`), `State`, `Plan`.*
- [x] **#21 — type mismatch `initialstate()` vs `precondition_pos`** — `Atom` vs tuple makes
      `issubset` always false. Resolve via the new `State` type so `operator.applicable(state)`
      works without manual casting. Linchpin: same change is both the bug fix and the planner's
      core data structure. *`State` normalizes Atom/tuple; `state.applicable(op)` / `state.apply(op)`.*
- [x] **Factor out grounding + successor generation** as shared components below the planner.
      *`GroundedTask` (grounds once; `successors(state)` + `is_goal(state)`).*
- [x] **Implement a blind-search reference planner** — BFS first, then A* / GBFS.
      *`BFSPlanner`, `AStarPlanner` (goal-count), `GBFSPlanner`; solve blocksworld + gripper.*
- [x] **Capability metadata + registry** (PRD §7); fail fast on unsupported `:requirements`.
      *`Planner.capabilities` + `check_capabilities`; `PlannerRegistry` (`register`/`get`).*
- [x] **#9 — enforce `:requirements`** — validate domain feature use against declared requirements.
      *Capture in model (`DomainProblem.requirements()`); `validate_requirements()` enforces
      typing/negative/disjunctive use vs declarations.*
- [x] **Boundary enforcement test** — planner imports nothing from grammar; model imports no
      planner code (import-linter rule or test). *`tests/test_layering.py` (static AST import scan).*
- [x] **#2 — API docs** — document the planner + model API (or defer per Open Question §9).
      *Docstrings throughout + README "Planning API" section; full docs site deferred.*

## Phase 2 — Numeric fluents  *(#11)*
- [x] Parse `:functions`, numeric preconditions, numeric effects. *`DomainProblem.functions()` +
      `initial_numeric()`; operators carry `precondition_num`/`effect_num`; numeric init captured.*
- [x] Object model: effect expressions; extend successor generation to evaluate them.
      *`Expr` tree (Num/Fluent/BinOp/Neg), `NumericConstraint`, `NumericEffect`; `State` carries a
      fluent valuation; BFS/A*/GBFS solve the numeric-transport domain. 100% coverage.*

## Phase 3 — Action costs
- [x] `total-cost` handling; `Plan` carries cost. *`:action-costs`/`:numeric-fluents` added to the
      grammar; `(:metric ...)` captured (`DomainProblem.metric()`); `Plan.cost` = accumulated
      `total-cost` (`costs.action_cost`/`plan_cost`, `TOTAL_COST`).*
- [x] Cost-aware search in the reference planner. *`UniformCostPlanner` ("ucs") is cost-optimal;
      on the travel domain UCS picks the cheaper 2-hop route (cost 2) vs BFS's 1-hop (cost 5).
      100% coverage.*

## Phase 4 — Durative actions  *(#23)*
- [x] **Complete duration-tag recovery** — grammar parses durative actions but Python recovery
      is incomplete (the known issue in CLAUDE.md). *Fixed: durative actions no longer crash the
      listener; duration recovered (`DurativeAction.duration`). Resolves #23/#27.*
- [x] **`DurativeAction` type** — time-tagged conditions/effects (`at start / over all / at end`).
      *`DurativeAction` with `condition_pos/neg` (start/over/end) and `effect_pos/neg` (start/end);
      `DomainProblem.durative_operators()` + `ground_durative_operator()`. 100% coverage.*
- [x] Decide temporal state representation; temporal-capable planner (or document non-coverage).
      *Documented non-coverage: the reference planners are non-temporal and do not solve durative
      domains (PRD §4/§8). The object model fully recovers durative actions.*

---

## Backlog / decisions
- [ ] **#10 — ADL** (conditional effects, quantifiers) — schedule after #13's precondition tree.
- [ ] **#12 — better variable binding** — revisit once grounding (#26) is fixed; may be subsumed.
- [x] **#22 — type super-sets** — typing hierarchy enhancement; Phase 2-ish. *Capture the
      `:types` subtype→supertype map (`DomainProblem.types()`/`subtypes_of()`); subtype-aware
      grounding (`_is_subtype`) so a supertype-typed param binds objects of any transitive
      subtype. logistics now grounds + solves. `(either ...)` union types still unhandled.*
- [ ] **#35 — HDDL parser** — decided **out of scope** (PRD §4). Reply and close.

## Done / merged
- [x] **Merge `ai-setup` branch** — CLAUDE.md setup (merged, #60).

---

*Last updated: 2026-06-14*
