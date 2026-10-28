# CLAUDE.md

## Project
Python PDDL parser + object model + reference planning layer (ANTLR4-based).
Four deliverables: the `pddlpy` library, a CLI (`pddlpy`), an MCP server
(`pddlpy-mcp`), and an Agent Skill (`skills/pddlpy/`).

## Quick Commands
```bash
uv sync           # Setup environment
make              # Run all tests (grammar + python)
make pyparser     # Regenerate parser from pddl.g4 (needs Java; commit the output)
make lint         # ruff
make typecheck    # mypy
make coverage     # tests with coverage report
make build        # Build wheel/sdist
make examples     # Run the example showcase
make golden       # Regenerate IPC subset golden files; review the diff (#153)
make corpora      # Fetch full IPC corpora (pinned) into $CORPORA_DIR (default .corpora), ~3 GB, opt-in
make corpora-test # pddlpy over every fetched pair; report in $CORPORA_DIR/results; DOMAIN=... filters
                  # (Makefile reads KEY=value lines from an optional .env, e.g. CORPORA_DIR=/Volumes/ext/corpora;
                  #  shell-style quotes are stripped by scripts/dotenv.sh)
make oracles      # Build Fast Downward / VAL / INVAL (pinned) into $ORACLES_DIR (default .oracles)
make oracle       # pytest -m oracle: pddlpy vs FD/VAL/INVAL; missing tools skip; ORACLE_CORPORA=1 for full corpora
                  # (CORPORA_PER_DOMAIN=N samples N problems per domain variant, also for corpora-test)
uv run pddlpy parse|ground|solve|validate DOMAIN PROBLEM   # the CLI
uv run pddlpy validate-plan|simulate DOMAIN PROBLEM PLAN  # plan checks (#166)
uv run pddlpy-mcp # MCP server on stdio
```

## Key Files
- `pddl.g4` — ANTLR4 grammar definition
- `pddlpy/pddl.py` — Object model (DomainProblem, Operator, Atom, DurativeAction)
- `pddlpy/binding.py` — Pluggable variable binders (StaticPrunedBinder default)
- `pddlpy/planning/` — State/Plan/GroundedTask, Planner ABC + registry, bfs/astar/gbfs/ucs/temporal
- `pddlpy/cli.py` + `pddlpy/serialize.py` — CLI (#85) and its JSON renderings
- `pddlpy/mcpserver.py` — MCP server, tools parse/ground/solve/validate/validate_plan/simulate (#86, #166)
- `pddlpy/diagnostics.py` — `diagnose()` behind `validate` (#94)
- `pddlpy/planning/validation.py` — `validate_plan` / `simulate`, VAL semantics (#166);
  probes shared with the oracle suite in `tests/validation_cases.py`
- `tests/` — the pytest suite (+ `tests/corpus/` PDDL pairs); `pddlpy/test.py` is legacy unittest
- `tests/corpus/ipc/` + `tests/golden.py` — IPC subset and its golden files
  (`test_golden.py`). A semantics change shows up as a golden mismatch:
  `make golden`, then review the diff (#153)
- `tests/oracles.py` + `tests/test_oracle.py` — external oracle wrappers and the
  `oracle`-marked checks (deselected by default). `tests/plans.py` writes the
  valid + corrupted plan fixtures under `tests/corpus/ipc/*/plans/`
- `docs/object-model.md`, `docs/llm-interaction.md` — reference + LLM worked example

## Architecture
```
pddl.g4 → (make pyparser) → pddlLexer/Parser/Listener (generated, committed)
                                    ↓
                    pddlpy/pddl.py  (object model)  ← pddlpy/diagnostics.py
                                    ↓
                    pddlpy/planning/ (imports model, NEVER the grammar —
                                      enforced by tests/test_layering.py)
                                    ↓
              pddlpy/cli.py, pddlpy/mcpserver.py  (via pddlpy/serialize.py)
```

## API Usage
```python
from pddlpy import DomainProblem
from pddlpy.planning import get
dp = DomainProblem("domain.pddl", "problem.pddl")
dp.initialstate(); dp.goals()        # sets of Atom (NO value equality — use
                                     # pddlpy.planning.atom_tuple to compare)
dp.ground_operator("move")           # grounded Operators (tuples inside)
plan = get("astar").solve(dp)        # or bfs/gbfs/ucs/temporal; None if unsolvable
```

## Dev Workflow
1. Edit `pddl.g4` (grammar) or the module in question
2. `make pyparser` if grammar changed
3. `make` to test; `make lint` + `make typecheck` before pushing
4. CI (`.github/workflows/ci.yaml`) runs tests (no Java) + 100%-coverage gate + ruff + mypy, plus a Java `grammar` job, on every PR
5. `.github/workflows/oracle.yaml` (#153) is NOT a PR gate: weekly, `workflow_dispatch`
   (run it before a release), and on pushes to main touching pddl.g4 / pddl.py /
   diagnostics.py / _vendor. It builds FD/VAL/INVAL, samples the corpora
   (`CORPORA_PER_DOMAIN`), and uploads a report. The `subset` job is strict (known
   disagreements are strict xfails in `KNOWN`, tests/test_oracle.py); the corpus jobs
   are report-only (disagreements → job summary + warning; each tagged with its known
   cause from `KNOWN_CAUSES` in tests/oracle_report.py, else **NEW**). After fixing a
   pddlpy bug, drop its entries from `KNOWN` and `KNOWN_CAUSES`. Coverage map:
   `docs/oracle-coverage.md`.
   GitHub disables scheduled workflows in public repos after 60 days without repo
   activity; re-enable it from the Actions tab.

## Conventions
- Grounded atoms are tuples `("predicate", "arg1", ...)`; ungrounded are `Atom`s
- Strict layering: planning never imports the grammar (test-enforced)
- Generated parser files are committed; CI's `grammar` job regenerates them and
  fails on drift. Java is needed only to change the grammar
- Zero runtime deps: the ANTLR runtime is vendored in `pddlpy/_vendor/antlr4`
  (excluded from ruff/mypy/coverage). Import it as `pddlpy._vendor.antlr4`,
  never `antlr4`; `make pyparser` rewrites the generated imports
- PDDL files are read as UTF-8 (#103)
- Python 3.11+; Java only for grammar compilation; `mcp` is an optional extra (`pddlpy[mcp]`)

## Release
1. Branch; bump version in `pyproject.toml`; add CHANGELOG entry; PR; merge.
2. Tag the release commit: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`.
3. GitHub Actions (`publish.yaml`) builds and publishes TestPyPI → PyPI via
   Trusted Publishing — there is NO local publish path (#96). The `pypi`
   environment requires manual approval in the Actions UI.
4. `gh release create vX.Y.Z` with notes + the CI-built dist artifacts.

## Known Issue
None outstanding. Type hierarchies (#22) supported (supertype binds transitive
subtypes); `(either ...)` union types remain unhandled. Durative actions are
solved by the `temporal` planner under sequential semantics only (no required
concurrency).

## Style
- Follow YAGNI principle.
- 100% of coverage in unit test (CI-enforced).
