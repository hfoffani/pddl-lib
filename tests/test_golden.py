"""Golden check on the curated IPC subset (#153).

Recomputes each pair's snapshot (see tests/golden.py) and compares it with
the committed golden file. A mismatch means parsing semantics changed: if
the change is intended, run ``make golden`` and commit the new files.
"""
import json
import os

import pytest
from golden import IPC, dumps, golden_path, pairs, snapshot

from pddlpy import DomainProblem

PAIRS = pairs()


def test_subset_present():
    assert len(PAIRS) >= 20


def test_snapshot_covers_adl_semantics(monkeypatch):
    """Losing the grounded precondition tree or the conditional effects must
    change the snapshot (review on #154)."""
    domain, problem = next(p for p in PAIRS if "elevator-adl-full-typed" in p[1])
    before = snapshot(domain, problem)
    assert all(len(g["conditional_effects"]) == 3 for g in before["ground"]["stop"])
    original = DomainProblem.ground_operator

    def stripped(self, name):
        for g in original(self, name):
            g.precondition, g.conditional_effects = None, []
            yield g

    monkeypatch.setattr(DomainProblem, "ground_operator", stripped)
    after = snapshot(domain, problem)
    assert after["ground"]["stop"] != before["ground"]["stop"]
    assert after["ground"]["up"] != before["ground"]["up"]


@pytest.mark.parametrize(
    "domain,problem",
    PAIRS,
    ids=[os.path.relpath(p, IPC) for _, p in PAIRS],
)
def test_golden(domain, problem):
    path = golden_path(problem)
    assert os.path.exists(path), "no golden file; run `make golden`"
    with open(path, encoding="utf-8") as f:
        expected = json.load(f)
    # Round-trip through JSON so tuples and lists compare alike.
    actual = json.loads(dumps(snapshot(domain, problem)))
    assert actual == expected, "golden mismatch; if intended, run `make golden`"
