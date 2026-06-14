"""#11 numeric fluents — model layer: parsing, grounding, evaluation."""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.pddl import Num, Fluent, BinOp, Neg, NumericConstraint, NumericEffect

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _transport():
    return DomainProblem(
        os.path.join(CORPUS, "numeric-transport-domain.pddl"),
        os.path.join(CORPUS, "numeric-transport-problem.pddl"),
    )


# -- model parsing ------------------------------------------------------------
def test_functions_declared():
    dp = _transport()
    funcs = dp.functions()
    assert set(funcs) == {"fuel", "fuel-cost"}
    assert funcs["fuel"] == [("?v", "vehicle")]
    assert funcs["fuel-cost"] == [("?from", "location"), ("?to", "location")]


def test_numeric_init():
    dp = _transport()
    init = dp.initial_numeric()
    assert init[("fuel", "truck")] == 100.0
    assert init[("fuel-cost", "a", "b")] == 30.0
    assert init[("fuel-cost", "b", "c")] == 40.0


def test_numeric_precondition_and_effect_captured():
    dp = _transport()
    op = dp.domain.operators["drive"]
    assert len(op.precondition_num) == 1
    assert op.precondition_num[0].comp == ">="
    assert len(op.effect_num) == 1
    assert op.effect_num[0].op == "decrease"


def test_grounding_substitutes_numeric():
    dp = _transport()
    drive_ab = next(
        g
        for g in dp.ground_operator("drive")
        if g.variable_list == {"?v": "truck", "?from": "a", "?to": "b"}
    )
    constraint = drive_ab.precondition_num[0]
    assert constraint.lhs.head == ("fuel", "truck")
    assert constraint.rhs.head == ("fuel-cost", "a", "b")
    effect = drive_ab.effect_num[0]
    assert effect.head.head == ("fuel", "truck")


# -- expression evaluation ----------------------------------------------------
def test_expr_evaluation():
    valuation = {("fuel", "truck"): 100.0, ("fuel-cost", "a", "b"): 30.0}
    assert Num(5).value(valuation) == 5.0
    assert Fluent(("fuel", "truck")).value(valuation) == 100.0
    assert Fluent(("missing",)).value(valuation) == 0.0  # default
    assert BinOp("+", Num(2), Num(3)).value(valuation) == 5.0
    assert BinOp("-", Num(2), Num(3)).value(valuation) == -1.0
    assert BinOp("*", Num(2), Num(3)).value(valuation) == 6.0
    assert BinOp("/", Num(6), Num(3)).value(valuation) == 2.0
    assert Neg(Num(4)).value(valuation) == -4.0


def test_numeric_constraint_holds():
    valuation = {("fuel", "truck"): 100.0}
    fuel = Fluent(("fuel", "truck"))
    assert NumericConstraint(">=", fuel, Num(30)).holds(valuation)
    assert not NumericConstraint(">=", fuel, Num(200)).holds(valuation)
    assert NumericConstraint("<", fuel, Num(200)).holds(valuation)
    assert NumericConstraint("=", fuel, Num(100)).holds(valuation)
    assert NumericConstraint(">", fuel, Num(99)).holds(valuation)
    assert NumericConstraint("<=", fuel, Num(100)).holds(valuation)


@pytest.mark.parametrize(
    "op,expected",
    [
        ("assign", 30.0),
        ("increase", 130.0),
        ("decrease", 70.0),
        ("scale-up", 3000.0),
        ("scale-down", 100.0 / 30.0),
    ],
)
def test_numeric_effect_apply(op, expected):
    valuation = {("fuel", "truck"): 100.0}
    eff = NumericEffect(op, Fluent(("fuel", "truck")), Num(30))
    key, new = eff.apply(valuation)
    assert key == ("fuel", "truck")
    assert new == pytest.approx(expected)


def test_expr_repr():
    assert repr(Num(3)) == "3.0"
    assert repr(Fluent(("fuel", "truck"))) == "('fuel', 'truck')"
    assert "+" in repr(BinOp("+", Num(1), Num(2)))
    assert repr(Neg(Num(1))).startswith("(-")
    assert ">=" in repr(NumericConstraint(">=", Num(1), Num(2)))
    assert "decrease" in repr(NumericEffect("decrease", Fluent(("f",)), Num(1)))
