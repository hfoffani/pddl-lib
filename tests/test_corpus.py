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
    ("numeric-transport", {"drive"}),
    ("travel", {"move"}),
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


def test_uppercase_keywords_parse():
    """#20 / #36: uppercase PDDL keywords ((:INIT ...), (DEFINE ...)) must
    parse identically to lowercase (identifiers too, #157)."""
    domainfile = os.path.join(CORPUS, "blocksworld-domain.pddl")
    upper = DomainProblem(
        domainfile, os.path.join(CORPUS, "blocksworld-upper-problem.pddl")
    )
    lower = DomainProblem(
        domainfile, os.path.join(CORPUS, "blocksworld-problem.pddl")
    )
    # initialstate()/goals() hold Atom objects without value equality (#21),
    # so compare by their string (tuple) representation.
    def as_strs(atoms):
        return sorted(str(a) for a in atoms)

    assert as_strs(upper.initialstate()) == as_strs(lower.initialstate())
    assert as_strs(upper.goals()) == as_strs(lower.goals())
    assert len(upper.initialstate()) == 7


def test_untyped_worldobjects_exclude_predicate_names():
    """Untyped domains must not leak predicate names into worldobjects():
    blocksworld declares no :types and no :constants, so world objects are
    exactly the :objects of the problem."""
    dp = DomainProblem(
        os.path.join(CORPUS, "blocksworld-domain.pddl"),
        os.path.join(CORPUS, "blocksworld-problem.pddl"),
    )
    assert dp.worldobjects() == {"a": None, "b": None, "c": None}
    groundings = list(dp.ground_operator("pick-up"))
    assert len(groundings) == 3
    assert {g.variable_list["?x"] for g in groundings} == {"a", "b", "c"}


@pytest.mark.parametrize("objects_section", ["", "(:objects)"])
def test_inferred_objects_keep_constant_types(tmp_path, objects_section):
    """#160: with no problem :objects, objects inferred (untyped) from :init
    and :goal must not override the domain's typed :constants. Many constants
    make the old hash-order-dependent merge fail reliably."""
    names = [f"plane_{i}" for i in range(64)]
    constants = dict.fromkeys([*names, "unused"], "airplane")
    domain = tmp_path / "domain.pddl"
    problem = tmp_path / "problem.pddl"
    domain.write_text(
        "(define (domain airport) (:requirements :strips :typing)"
        " (:types airplane)"
        f" (:constants {' '.join(constants)} - airplane)"
        " (:predicates (ready ?p - airplane) (done ?p - airplane) (marker ?x))"
        " (:action move :parameters (?p - airplane)"
        " :precondition (ready ?p) :effect (done ?p)))"
    )
    problem.write_text(
        "(define (problem flight) (:domain airport)"
        f" {objects_section}"
        f" (:init {' '.join(f'(ready {n})' for n in names)} (marker init_only))"
        " (:goal (and (done plane_0) (marker goal_only))))"
    )
    dp = DomainProblem(str(domain), str(problem))
    assert all(dp.problem.objects[n] is None for n in names)

    objects = dp.worldobjects()
    assert {n: objects[n] for n in constants} == constants
    assert objects["init_only"] is None
    assert objects["goal_only"] is None
    assert set(dp.candidate_objects("airplane")) == set(constants)
    assert {op.variable_list["?p"] for op in dp.ground_operator("move")} == set(names)


def test_trailing_comment_without_newline(tmp_path):
    """#19: a comment on the final line with no trailing newline must not
    break the lexer."""
    problem = tmp_path / "p.pddl"
    # Written with no trailing newline after the comment.
    problem.write_text(
        "(define (problem p)\n"
        "  (:domain blocksworld)\n"
        "  (:objects a b)\n"
        "  (:init (clear a))\n"
        "  (:goal (and (on a b))))\n"
        "; trailing comment with no newline",
        newline="",
    )
    assert not problem.read_text().endswith("\n")
    domainfile = os.path.join(CORPUS, "blocksworld-domain.pddl")
    dp = DomainProblem(domainfile, str(problem))
    assert len(dp.initialstate()) == 1
    assert len(dp.goals()) == 1
