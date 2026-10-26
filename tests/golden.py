"""Golden files for the curated IPC subset (#153).

Each ``tests/corpus/ipc/<domain>/pNN.pddl`` pairs with that directory's
``domain.pddl``; its golden file ``pNN.json`` freezes what pddlpy makes of
the pair: the ``parse`` summary, the grounded operators (capped per
operator), and the ``validate`` verdict. A pair that crashes the loader
records the exception instead.

``tests/test_golden.py`` recomputes every snapshot and compares. After an
intended change in parsing semantics, regenerate with ``make golden`` and
review the diff.
"""
from __future__ import annotations

import glob
import json
import os
from itertools import islice
from typing import Any, Dict, List, Tuple

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.pddl import And, Lit, Not, Or
from pddlpy.planning import atom_tuple
from pddlpy.serialize import atoms_list, domain_problem_dict, operator_dict

IPC = os.path.join(os.path.dirname(__file__), "corpus", "ipc")

# Groundings kept per operator. Past it the snapshot records only that the
# cap was hit, which keeps golden files small and generation fast.
GROUND_CAP = 50


def pairs() -> List[Tuple[str, str]]:
    """Every (domain, problem) path pair in the subset, sorted."""
    return [
        (os.path.join(os.path.dirname(p), "domain.pddl"), p)
        for p in sorted(glob.glob(os.path.join(IPC, "*", "p[0-9]*.pddl")))
    ]


def golden_path(problem: str) -> str:
    return os.path.splitext(problem)[0] + ".json"


def condition(c: Any) -> str:
    """Canonical text of a grounded condition tree. Quantifiers ground to
    and/or over instances in binder order, so children are sorted."""
    if isinstance(c, Lit):
        return "(%s)" % " ".join(atom_tuple(c.atom))
    if isinstance(c, Not):
        return "(not %s)" % condition(c.child)
    if isinstance(c, (And, Or)):
        word = "and" if isinstance(c, And) else "or"
        return "(%s %s)" % (word, " ".join(sorted(condition(k) for k in c.children)))
    return repr(c)  # Equality, NumericCond


def grounded_operator(op: Any) -> Dict[str, Any]:
    """``operator_dict`` plus the executable ADL semantics: the grounded
    precondition tree and the conditional effects."""
    result = operator_dict(op)
    tree = getattr(op, "precondition", None)
    result["precondition"] = None if tree is None else condition(tree)
    result["conditional_effects"] = sorted(
        (
            {
                "condition": condition(ce.condition),
                "add": atoms_list(ce.add),
                "del": atoms_list(ce.dele),
                "num": sorted(repr(n) for n in ce.num),
            }
            for ce in getattr(op, "conditional_effects", ())
        ),
        key=lambda d: json.dumps(d, sort_keys=True),
    )
    return result


def _capped(groundings: Any, render: Any) -> Any:
    head = list(islice(groundings, GROUND_CAP + 1))
    if len(head) > GROUND_CAP:
        return {"truncated_at": GROUND_CAP}
    # Grounding order follows set iteration; sort for a stable snapshot.
    return sorted((render(g) for g in head), key=lambda d: json.dumps(d, sort_keys=True))


def snapshot(domain: str, problem: str) -> Dict[str, Any]:
    """What pddlpy makes of one pair, as JSON-able data."""
    result: Dict[str, Any] = {}
    try:
        dp = DomainProblem(domain, problem)
        result["parse"] = domain_problem_dict(dp)
        result["ground"] = {
            op: _capped(dp.ground_operator(op), grounded_operator)
            for op in sorted(dp.operators())
        }
        result["ground_durative"] = {
            op: _capped(
                dp.ground_durative_operator(op),
                lambda g: {"name": g.operator_name, "parameters": dict(g.variable_list)},
            )
            for op in sorted(dp.durative_operators())
        }
    except Exception as exc:  # the crash itself is the behaviour to freeze
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
    try:
        result["validate"] = diagnose(domain, problem)
    except Exception as exc:
        result["validate"] = {"error": {"type": type(exc).__name__, "message": str(exc)}}
    return result


def dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def main() -> None:
    for domain, problem in pairs():
        with open(golden_path(problem), "w", encoding="utf-8") as f:
            f.write(dumps(snapshot(domain, problem)))
        print(os.path.relpath(golden_path(problem)))


if __name__ == "__main__":
    main()
