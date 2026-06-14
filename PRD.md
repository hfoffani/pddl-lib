# PRD: Parser Hardening, Planner Interface & PDDL Feature Expansion

> **Status:** Refined draft
> **Owner:** Hernán
> **Project:** `pddlpy` (Python PDDL parser + object model)

---

## 1. Context

The library provides a PDDL pipeline:

```
ANTLR4 grammar → parse tree → listener → domain/problem object model
```

It parses STRIPS + typing into a `DomainProblem` / `Operator` / `Atom` model. It does
**not** yet solve anything — the object model is the ceiling — and, despite the prior
draft's claim, it does **not** reliably validate: standard IPC benchmarks fail to parse
and several constructs are silently mis-handled (see §2). There is **1** unit test.

This PRD covers three tracks, in dependency order:

0. **Harden the foundation** — fix the parser/model correctness bugs that block real use,
   and build a test+coverage safety net so the layers above can be trusted.
1. **Introduce a planner/solver layer** with a stable, pluggable interface.
2. **Expand the supported PDDL subset** beyond STRIPS (numeric fluents, action costs,
   durative actions), the object model evolving to support each.

The guiding constraint remains a **strict layered architecture** — each layer depends only
on the one below it, no leakage upward.

```
┌─────────────────────────────────────┐
│  Planner interface (solve)           │  ← new   (Phase 1)
├─────────────────────────────────────┤
│  Domain / Problem object model       │  ← fix + extend  (Phase 0, then 2–4)
├─────────────────────────────────────┤
│  ANTLR4 grammar + parser/listener    │  ← fix + extend  (Phase 0, then 2–4)
└─────────────────────────────────────┘
```

---

## 2. Foundation problems (why Phase 0 exists)

The previous PRD assumed a "working, validating pipeline" and went straight to a planner.
Verification shows the foundation is not yet planner-ready. A planner stands precisely on
correct grounding, correct preconditions, and comparable states — the things currently
broken:

| # | Symptom | Impact on a planner |
|---|---------|---------------------|
| #36 / #20 | Keywords are case-sensitive; `(:INIT ...)` in standard IPC files isn't recognized. `initialstate()` comes back **empty, no error**. Reproduced on IPC blocksworld. | Phase 0-style "solve blocksworld/gripper" fails at the parse step. Silent. |
| #13 | `or` preconditions are flattened into the same flat positive/negative sets as `and`. No way to tell them apart. | Planner explores wrong state space; no error raised. |
| #26 | `vargroundspace` is cached across operators; grounding a second operator reuses the first's variable bindings. | Successor generation produces invalid actions. |
| #21 | `precondition_pos` holds tuples while `initialstate()` holds `Atom`s; they can't be compared/`issubset`. | Cannot check applicability — the core planner inner loop. |
| #19 | A comment on the final line (no trailing newline) breaks parsing. | Real files fail to load. |

**Conclusion:** building the planner before fixing these means building on sand. Phase 0
fixes the parsing and grounding bugs (#36/#20, #26, #19, #13) and locks them in with tests +
coverage before any planner code is written. **#21 is resolved in Phase 1**, where it is
inseparable from the `State` type the planner needs (§5.3).

---

## 3. Goals

- **Parse the standard STRIPS PDDL corpus correctly** (IPC blocksworld, gripper, logistics),
  with keyword case-insensitivity and the grounding/precondition bugs fixed.
- Establish a **measured test-coverage baseline** and drive line coverage toward 100%, using
  failing/xfail tests to *document* remaining bugs rather than hide them.
- Define an **abstract solver interface** so multiple planners can be registered and swapped
  without changing the parser or object model.
- Ship at least one **working reference planner** against STRIPS to prove the interface.
- Keep layer boundaries strict and enforced (no planner reaching into parse trees; object
  model imports no planner code).
- Establish an extension path for numeric fluents, action costs, and durative actions that
  does not require redesigning the interface each time.

## 4. Non-Goals

- Competing with Fast Downward / LAMA on performance. The reference planner proves the
  contract, it is not a benchmark entrant.
- Full PDDL 3.x (preferences, constraints, trajectory constraints) this round.
- HDDL (#35) — explicitly out of scope; record the decision and close.
- A CLI / service / MCP wrapper. Out of scope until the library API stabilizes.

---

## 5. Planner Interface Design (Phase 1)

### 5.1 Baseline contract

```python
class Planner(ABC):
    @abstractmethod
    def solve(self, domain: Domain, problem: Problem) -> Plan | None:
        ...
```

- Returns a `Plan` (ordered actions, optionally timestamps/costs) or `None` if no plan exists.
- `Domain` / `Problem` are the **already-fixed, validated** Phase 0 objects.

### 5.2 Interface granularity — decision

Keep `solve(domain, problem) -> Plan` as the *public* contract, but internally factor out
**grounding** and **successor generation** (`apply(state, action) -> state`) as shared,
reusable components below the planner. A blind-search planner uses only the successor
function; a future heuristic planner (FF/LAMA-style) reuses the same grounded representation
without re-deriving it. This is feasible only once #26 (grounding) and #21 (state/atom
typing) are fixed in Phase 0.

### 5.3 State representation

Introduce an immutable, hashable `State` so search can build closed/open sets. This is also
the clean resolution to #21 — `Operator.applicable(state)` and `state.apply(operator)` instead
of ad-hoc tuple/`Atom` comparison.

### 5.4 Registration

```python
registry.register("bfs", BFSPlanner)
registry.register("astar", AStarPlanner)
planner = registry.get("astar")
plan = planner.solve(domain, problem)
```

Capability metadata (costs? durations?) lets the caller pick a compatible planner — see §7.

---

## 6. Object Model Evolution

| Feature            | Object model impact |
|--------------------|---------------------|
| STRIPS (current)   | `Operator` with add/delete sets, positive/negative preconditions |
| OR / ADL (partial) | Precondition tree (and/or/not) instead of flat sets — needed to fix #13 honestly |
| Numeric fluents    | Effects become expressions, not add/delete; `:functions`; numeric preconditions (#11) |
| Action costs       | Special case of numeric fluents (`total-cost`); plan carries a cost |
| Durative actions   | Distinct `DurativeAction` type; conditions/effects tagged `at start / over all / at end` (#23) |

**Design notes:** durative actions are *not* an extension of `Operator` — model them as a
distinct type (state-transition model becomes temporal). Numeric fluents are the lower-risk
intermediate step, land them before durations. Fixing #13 (OR) properly forces a precondition
**tree** rather than flat sets; do this in Phase 0/early so the planner is built against the
real shape, not refactored later.

---

## 7. Capability Negotiation

Domains and planners declare capabilities, validated against PDDL `:requirements` (#9):

- The object model already knows what features a domain uses.
- Each planner declares what it supports.
- `solve()` / the registry **fails fast** with a clear error when a planner is handed a domain
  beyond its subset (e.g. a STRIPS-only planner given durative actions).

---

## 8. Phased Roadmap

**Phase 0 — Foundation: correctness + coverage** *(new, gating)*
- Fix keyword case-insensitivity (#20) → unblocks IPC parsing (#36).
- Fix last-line comment handling (#19).
- Fix grounding cross-operator cache bug (#26).
- Preserve the OR/AND/NOT precondition connective (#13) — at minimum stop silently flattening
  to AND. (Full ADL/DNF deferred to keep the phase short — see §6, #10.)
- Stand up coverage tooling; add a benchmark parse-corpus; drive coverage toward 100% with
  xfail markers documenting any bug not yet fixed.
- Fix the broken `make testgrammar` Java classpath so grammar changes stay verifiable.

**Phase 1 — Interface + reference planner (STRIPS)**
- Define `Planner` ABC and `Plan` / `State` types.
- Resolve state/atom type mismatch (#21) via the `State` type — comparable `State`/`Atom`
  semantics so `operator.applicable(state)` works without manual casting.
- Factor out grounding + successor generation as shared components.
- Implement a blind-search reference planner (BFS, then A* / GBFS).
- Capability metadata + registry.

**Phase 2 — Numeric fluents** (#11)
- Parse `:functions`, numeric preconditions, numeric effects.
- Object model: effect expressions. Extend successor generation to evaluate them.

**Phase 3 — Action costs**
- `total-cost` handling; `Plan` carries cost. Cost-aware search.

**Phase 4 — Durative actions** (#23)
- `DurativeAction` type; time-tagged conditions/effects. Temporal state representation.
- Temporal-capable planner, or document that the reference planner does not cover this.

---

## 9. Open Questions

- **Grounded vs lifted at the boundary:** does `solve` receive lifted actions and ground
  internally, or is grounding a separate pre-pass the caller can invoke?
- **OR depth in Phase 0:** full precondition tree + DNF evaluation now, or just preserve the
  connective and defer full ADL (#10) to a later phase?
- **Plan validation:** integrate a VAL-style validator to check produced plans? (We validate
  domain/problem; validating *plans* closes the loop.)
- **External planners:** does the same interface eventually wrap Fast Downward / LAMA via
  subprocess, or a separate adapter layer? Affects how `Plan` and errors are modeled.
- **API docs (#2):** generate docs in this round, or defer until the API stabilizes post-Phase 1?

## 10. Acceptance Criteria

**Phase 0**
- IPC blocksworld and gripper domain+problem pairs parse correctly; `initialstate()` and
  `goals()` are non-empty and match the files. (#36 regression test.)
- Grounding two different operators yields correct, independent variable bindings. (#26.)
- Coverage is measured and reported; line coverage at/near 100%, with every still-failing/xfail
  test traceable to a documented bug.

**Phase 1**
- A `Planner` ABC exists with `solve(domain, problem) -> Plan | None`.
- An operator's preconditions can be checked against a `State` without manual casting. (#21.)
- At least one planner solves canonical STRIPS problems (blocksworld, gripper) correctly.
- No planner module imports from the parser/grammar layer; the object model imports no planner
  code (enforced by an import-linter rule or test).
- A second planner registers and runs on the same problem without changing the layers below.
