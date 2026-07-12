# CLAUDE.md

## Project
Python PDDL parser + object model + reference planning layer (ANTLR4-based).
Four deliverables: the `pddlpy` library, a CLI (`pddlpy`), an MCP server
(`pddlpy-mcp`), and an Agent Skill (`skills/pddlpy/`).

## Quick Commands
```bash
uv sync           # Setup environment (fresh clone: run `make pyparser` FIRST)
make              # Run all tests (grammar + python, 191 tests)
make pyparser     # Regenerate parser from pddl.g4 (needs Java)
make lint         # ruff
make typecheck    # mypy
make coverage     # tests with coverage report
make build        # Build wheel/sdist
make examples     # Run the example showcase
uv run pddlpy parse|ground|solve|validate DOMAIN PROBLEM   # the CLI
uv run pddlpy-mcp # MCP server on stdio
```

## Key Files
- `pddl.g4` — ANTLR4 grammar definition
- `pddlpy/pddl.py` — Object model (DomainProblem, Operator, Atom, DurativeAction)
- `pddlpy/binding.py` — Pluggable variable binders (StaticPrunedBinder default)
- `pddlpy/planning/` — State/Plan/GroundedTask, Planner ABC + registry, bfs/astar/gbfs/ucs
- `pddlpy/cli.py` + `pddlpy/serialize.py` — CLI (#85) and its JSON renderings
- `pddlpy/mcpserver.py` — MCP server, tools parse/ground/solve/validate (#86)
- `pddlpy/diagnostics.py` — `diagnose()` behind `validate` (#94)
- `tests/` — the pytest suite (+ `tests/corpus/` PDDL pairs); `pddlpy/test.py` is legacy unittest
- `docs/object-model.md`, `docs/llm-interaction.md` — reference + LLM worked example

## Architecture
```
pddl.g4 → (make pyparser) → pddlLexer/Parser/Listener (generated, gitignored)
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
plan = get("astar").solve(dp)        # or bfs/gbfs/ucs; None if unsolvable
```

## Dev Workflow
1. Edit `pddl.g4` (grammar) or the module in question
2. `make pyparser` if grammar changed
3. `make` to test; `make lint` + `make typecheck` before pushing
4. CI (`.github/workflows/ci.yaml`) runs make + 100%-coverage gate + ruff + mypy on every PR

## Conventions
- Grounded atoms are tuples `("predicate", "arg1", ...)`; ungrounded are `Atom`s
- Strict layering: planning never imports the grammar (test-enforced)
- Generated parser files are gitignored but force-included in dist — on a fresh
  clone/CI, `make pyparser` must run BEFORE `uv sync` or the editable build fails
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
subtypes); `(either ...)` union types remain unhandled. Durative actions parse
and validate but are not temporally solved (#84 tracks a future temporal planner).

## Style
- Follow YAGNI principle.
- 100% of coverage in unit test (CI-enforced).
