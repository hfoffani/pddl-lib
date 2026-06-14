#!/usr/bin/env python
"""Smoke driver for the pddlpy library.

Exercises the full public API of pddlpy.DomainProblem against the bundled
example PDDL files and asserts known invariants. This is the programmatic
handle a future agent uses to confirm the parser works after a change to
the grammar (pddl.g4) or the listener logic (pddlpy/pddl.py).

Usage (run from the repo root so the example paths resolve):
    uv run python .claude/skills/run-pddlpy/smoke.py            # all examples
    uv run python .claude/skills/run-pddlpy/smoke.py 2          # one example

Exit code 0 = every checked invariant held. Non-zero = something broke.
"""
import sys

from pddlpy import DomainProblem

# operator that demo.py grounds for each example, plus a cheap invariant we
# can assert without hand-maintaining full expected output for every file.
KNOWN_OPS = {
    1: "op2",
    2: "move",
    3: "move",
    4: "move",
    6: "op2",
}


def check(example: int) -> None:
    domainfile = "examples-pddl/domain-0%d.pddl" % example
    problemfile = "examples-pddl/problem-0%d.pddl" % example
    print(f"=== example {example}: {domainfile} + {problemfile}")

    dp = DomainProblem(domainfile, problemfile)

    objects = dp.worldobjects()
    operators = list(dp.operators())
    init = dp.initialstate()
    goals = dp.goals()

    assert isinstance(objects, dict), "worldobjects() must be a dict"
    assert operators, "operators() returned nothing"
    assert isinstance(init, set) and init, "initialstate() must be a non-empty set"
    assert isinstance(goals, set) and goals, "goals() must be a non-empty set"

    # GOTCHA: initialstate()/goals() return pddlpy.pddl.Atom objects whose
    # repr looks like a tuple but are NOT tuples. Only grounded operator
    # pre/effects (below) are real tuples. Normalize via .predicate here.
    for atom in init | goals:
        pred = atom.predicate if hasattr(atom, "predicate") else atom
        assert tuple(pred), f"empty atom {atom!r}"

    print(f"    objects={len(objects)} operators={operators} "
          f"init={len(init)} goals={len(goals)}")

    # grounding: yield at least one grounded Operator and confirm its
    # variables resolved (no remaining '?' placeholders in the binding).
    op = KNOWN_OPS.get(example, operators[0])
    grounded = list(dp.ground_operator(op))
    assert grounded, f"ground_operator({op!r}) yielded nothing"
    sample = grounded[0]
    assert sample.operator_name == op
    for var, val in sample.variable_list.items():
        assert var.startswith("?"), f"variable name should keep '?': {var!r}"
        assert not str(val).startswith("?"), f"unbound variable {var}={val!r}"
    print(f"    ground_operator({op!r}) -> {len(grounded)} grounded instances; "
          f"sample vars={sample.variable_list}")
    print(f"    PASS example {example}")


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        examples = [int(a) for a in argv[1:]]
    else:
        examples = [1, 2, 3, 4, 6]  # 5 has no problem-grounding op in demo set
    for e in examples:
        check(e)
    print(f"\nALL OK ({len(examples)} example(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
