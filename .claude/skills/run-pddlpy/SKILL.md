---
name: run-pddlpy
description: Run, test, build, or smoke-check the pddlpy PDDL parser library. Use when asked to run pddlpy/pddl-lib, parse a PDDL domain/problem, exercise the DomainProblem API, ground operators, regenerate the ANTLR parser, or build the wheel.
---

# Run pddlpy

`pddlpy` is a **Python library** (no GUI, no server): an ANTLR4-based PDDL
parser exposing `DomainProblem` (parse domain+problem, read objects / initial
state / goals / operators, and ground operators). You drive it by
**importing and calling it** — the harness is
`.claude/skills/run-pddlpy/smoke.py`, which exercises the whole public API
against the bundled `examples-pddl/` files and asserts invariants.

All paths below are relative to the repo root (`pddl-lib/`). Run everything
from there.

## Prerequisites

- **uv** — manages the venv and runs Python. `uv sync` installs deps
  (just `antlr4-python3-runtime==4.13.2`).
- **Java 11+** — only needed to (re)generate the parser or `make build`
  (the `pyparser` step shells out to `antlr-4.13.2-complete.jar`). Verified
  here with `java 15`. Pure import/test of an already-generated tree does
  not need Java. (Verified on macOS; on Ubuntu: `apt-get install -y default-jre`.)

## Build (required on a fresh clone)

The generated parser (`pddlpy/pddlLexer.py`, `pddlParser.py`,
`pddlListener.py`) is **gitignored** — a fresh checkout has none of it and
`import pddlpy` will fail until you generate it:

```bash
uv sync          # create .venv, install antlr4 runtime
make pyparser    # generate pddlLexer/pddlParser/pddlListener into pddlpy/ (needs Java)
```

## Run (agent path) — the smoke driver

This is the path to use. It parses every example, calls `worldobjects()`,
`operators()`, `initialstate()`, `goals()`, and `ground_operator()`, and
asserts the results are well-formed. Exit 0 = all good.

```bash
uv run python .claude/skills/run-pddlpy/smoke.py        # all examples (1,2,3,4,6)
uv run python .claude/skills/run-pddlpy/smoke.py 2      # just example 2
```

Expected tail:

```
ALL OK (5 example(s) checked)
```

Minimal direct invocation (drop into a one-off check):

```bash
uv run python -c "
from pddlpy import DomainProblem
dp = DomainProblem('examples-pddl/domain-02.pddl','examples-pddl/problem-02.pddl')
print(list(dp.operators()))
print(next(iter(dp.ground_operator('move'))))
"
```

## Test

```bash
make            # grammar test (Java GRUN) + python unittest — the full suite
uv run python -m pddlpy.test    # python unit test only (no Java)
make demo       # run demo.py over examples 1,2,3,4,6 (human-readable dump)
```

`make build` runs the python tests, regenerates the parser, then `uv build`
produces `dist/pddlpy-<ver>.tar.gz` and `.whl`.

## Gotchas

- **`initialstate()` / `goals()` return `Atom` objects, NOT tuples** —
  their `__repr__` prints as `('on','ca','pallet')` so they *look* like
  tuples, but `isinstance(x, tuple)` is `False`. Use `x.predicate` (a list)
  to get the symbols. By contrast, a **grounded** operator's
  `precondition_pos`/`effect_pos`/etc. ARE real `tuple`s. `smoke.py`
  normalizes both via `hasattr(atom, "predicate")`.
- **Generated parser is gitignored** — see Build. Forgetting `make pyparser`
  on a fresh clone gives `ModuleNotFoundError: pddlpy.pddlLexer`.
- **`ground_operator` returns a generator** — wrap in `list()` to count or
  re-iterate. It can explode combinatorially on untyped domains (example 1's
  `op2` grounds to 125 instances from 5 symbols × 3 vars).
- **Run from the repo root** — example paths (`examples-pddl/...`) and the
  test are relative; running elsewhere breaks `FileStream`.
- **`.claude/` is gitignored** in this repo, so this skill (and `smoke.py`)
  won't be committed by a plain `git add`. Use `git add -f` if you want them
  tracked.

## Troubleshooting

- `ModuleNotFoundError: No module named 'pddlpy.pddlLexer'` → run
  `make pyparser` (parser not generated).
- `make pyparser` fails with a Java error → install a JRE (`java -version`
  must work); the `antlr-4.13.2-complete.jar` is committed at the repo root.
- `FileNotFoundError` on `examples-pddl/...` → you're not in the repo root.
