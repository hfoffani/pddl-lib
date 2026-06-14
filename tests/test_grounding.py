"""#26 regression: grounding two different operators must yield correct,
independent variable bindings regardless of grounding order.

The cross-operator cache (`vargroundspace`) is keyed per operator name;
these tests guard against a regression where one operator's bindings
leak into another's.
"""
import os

import pytest

from pddlpy import DomainProblem

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _bindings(domprob, op_name):
    """Set of grounded variable bindings for an operator, order-independent."""
    return {
        frozenset(gop.variable_list.items())
        for gop in domprob.ground_operator(op_name)
    }


@pytest.fixture
def gripper():
    return DomainProblem(
        os.path.join(CORPUS, "gripper-domain.pddl"),
        os.path.join(CORPUS, "gripper-problem.pddl"),
    )


def test_two_operators_independent(gripper):
    move = _bindings(gripper, "move")
    pick = _bindings(gripper, "pick")
    # move binds only ?from/?to over rooms; pick binds ?obj/?room/?gripper.
    assert all({"?from", "?to"} == {v for v, _ in b} for b in move)
    assert all({"?obj", "?room", "?gripper"} == {v for v, _ in b} for b in pick)
    # 2 rooms ^2 = 4 moves; 2 balls * 2 rooms * 2 grippers = 8 picks.
    assert len(move) == 4
    assert len(pick) == 8


def test_grounding_order_independent(gripper):
    # Ground pick first, then move, on a fresh instance, and compare to
    # grounding them in the opposite order.
    pick_first = _bindings(gripper, "pick")
    move_after = _bindings(gripper, "move")

    other = DomainProblem(
        os.path.join(CORPUS, "gripper-domain.pddl"),
        os.path.join(CORPUS, "gripper-problem.pddl"),
    )
    move_first = _bindings(other, "move")
    pick_after = _bindings(other, "pick")

    assert pick_first == pick_after
    assert move_after == move_first


def test_shared_varname_different_type(tmp_path):
    """Two operators reusing the same variable name (?x) with different
    types must ground over their own type's objects."""
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d)\n"
        " (:requirements :strips :typing)\n"
        " (:types animal tool)\n"
        " (:predicates (p ?x - animal) (q ?x - tool))\n"
        " (:action acta :parameters (?x - animal)"
        "   :precondition (p ?x) :effect (not (p ?x)))\n"
        " (:action actb :parameters (?x - tool)"
        "   :precondition (q ?x) :effect (not (q ?x))))\n"
    )
    problem.write_text(
        "(define (problem p) (:domain d)\n"
        " (:objects cat dog - animal hammer saw - tool)\n"
        " (:init (p cat)) (:goal (p cat)))\n"
    )
    dp = DomainProblem(str(domain), str(problem))
    acta = {next(iter(b))[1] for b in _bindings(dp, "acta")}
    actb = {next(iter(b))[1] for b in _bindings(dp, "actb")}
    assert acta == {"cat", "dog"}
    assert actb == {"hammer", "saw"}
