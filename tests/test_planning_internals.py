"""Coverage-driven tests for planning internals: reprs, normalization,
best-first failure path, and negative-precondition feature detection."""
import os

from pddlpy import DomainProblem
from pddlpy.planning import AStarPlanner, GBFSPlanner, Plan, State
from pddlpy.planning.base import _used_features
from pddlpy.planning.state import atom_tuple

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def test_atom_tuple_from_list():
    # fallback branch: neither a tuple nor an Atom with .predicate
    assert atom_tuple(["on", "a", "b"]) == ("on", "a", "b")


def test_state_iter_and_repr():
    s = State([("clear", "a"), ("on", "b", "c")])
    assert set(iter(s)) == {("clear", "a"), ("on", "b", "c")}
    assert repr(s).startswith("State(")


def test_plan_repr():
    dp = DomainProblem(
        os.path.join(CORPUS, "blocksworld-domain.pddl"),
        os.path.join(CORPUS, "blocksworld-problem.pddl"),
    )
    op = next(o for o in dp.ground_operator("pick-up") if o.variable_list["?x"] == "a")
    text = repr(Plan([op]))
    assert text.startswith("Plan[cost=1]")
    assert "pick-up" in text


def test_negative_precondition_feature(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips :negative-preconditions)\n"
        " (:predicates (p ?x) (q ?x))\n"
        " (:action a :parameters (?x) :precondition (not (q ?x)) :effect (p ?x)))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o) (:init (q o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    assert "negative-preconditions" in _used_features(dp)


def _unsolvable(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips) (:predicates (p ?x) (q ?x))\n"
        " (:action a :parameters (?x) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o) (:init (p o)) (:goal (q o)))"
    )
    return DomainProblem(str(domain), str(problem))


def test_best_first_unsolvable_returns_none(tmp_path):
    dp = _unsolvable(tmp_path)
    assert AStarPlanner().solve(dp) is None
    assert GBFSPlanner().solve(dp) is None
