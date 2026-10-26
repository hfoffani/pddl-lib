"""The committed plan fixtures (tests/plans.py, #153) are what they claim:
pddlpy replays each valid plan to the goal and rejects every corruption."""
import os

import pytest
from oracles import read_plan, replay
from plans import corruptions, fixtures

from pddlpy import DomainProblem

FIXTURES = fixtures()


def pair(plan_path):
    plans = os.path.dirname(plan_path)
    stem = os.path.basename(plan_path).split(".")[0]
    root = os.path.dirname(plans)
    return os.path.join(root, "domain.pddl"), os.path.join(root, stem + ".pddl")


def test_fixtures_present():
    assert len(FIXTURES) >= 2


@pytest.mark.parametrize("plan", FIXTURES, ids=lambda p: os.path.relpath(p, "tests/corpus/ipc"))
def test_fixture(plan):
    dp = DomainProblem(*pair(plan))
    assert replay(dp, read_plan(plan)) is None
    for kind in corruptions(read_plan(plan)):
        bad = plan[: -len(".plan")] + ".%s.plan" % kind
        assert replay(dp, read_plan(bad)) is not None, kind
