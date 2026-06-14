"""Benchmark parse-corpus: canonical IPC domains that MUST parse.

This is the #36 regression guard. Each domain/problem pair below has to
load, expose the operators declared in the domain, and yield a non-empty
initial state and goal. If any of these regress, real-world PDDL files
have stopped parsing.
"""
import os

import pytest

from pddlpy import DomainProblem

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")

# (name, expected operator names)
BENCHMARKS = [
    ("blocksworld", {"pick-up", "put-down", "stack", "unstack"}),
    ("gripper", {"move", "pick", "drop"}),
    (
        "logistics",
        {
            "load-truck",
            "load-airplane",
            "unload-truck",
            "unload-airplane",
            "drive-truck",
            "fly-airplane",
        },
    ),
]


@pytest.fixture(params=BENCHMARKS, ids=[b[0] for b in BENCHMARKS])
def benchmark(request):
    name, expected_ops = request.param
    domainfile = os.path.join(CORPUS, "%s-domain.pddl" % name)
    problemfile = os.path.join(CORPUS, "%s-problem.pddl" % name)
    return DomainProblem(domainfile, problemfile), expected_ops


def test_operators_present(benchmark):
    dp, expected_ops = benchmark
    assert set(dp.operators()) == expected_ops


def test_initial_state_non_empty(benchmark):
    dp, _ = benchmark
    assert len(dp.initialstate()) > 0


def test_goals_non_empty(benchmark):
    dp, _ = benchmark
    assert len(dp.goals()) > 0
