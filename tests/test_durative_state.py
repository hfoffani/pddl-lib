"""#23: durative-action validation + `at start` applicability (DurativeState).

These exercise the semantic layer above the durative object model — structural
validation and start-condition applicability — without any temporal planning,
which stays out of scope.
"""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.pddl import Atom, DurativeAction
from pddlpy.planning import (
    DurativeState,
    DurativeValidationError,
    validate_durative_action,
    validate_durative_actions,
)

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp():
    return DomainProblem(
        os.path.join(CORPUS, "durative-action-domain.pddl"),
        os.path.join(CORPUS, "durative-action-problem.pddl"),
    )


def _grounded(dp, **binding):
    for g in dp.ground_durative_operator("go"):
        if g.variable_list == binding:
            return g
    raise AssertionError("no grounding %r" % binding)


def _synthetic(duration=1.0):
    """A grounded-style durative action touching every condition/effect bucket
    (predicates 'at'/'road'/'visited', no free variables)."""
    da = DurativeAction("full")
    da.duration = duration
    da.condition_pos["start"] = {("at", "a")}
    da.condition_pos["over"] = {("road", "a", "b")}
    da.condition_pos["end"] = {("road", "a", "b")}
    da.condition_neg["start"] = {("visited", "a")}
    da.effect_pos["end"] = {("at", "b"), ("visited", "b")}
    da.effect_neg["start"] = {("at", "a")}
    return da


# -- predicates() accessor ------------------------------------------------
def test_predicates_accessor():
    assert _dp().predicates() == {"at", "visited", "road"}


# -- DurativeState --------------------------------------------------------
def test_from_problem_atoms():
    ds = DurativeState.from_problem(_dp())
    assert ("at", "a") in ds
    assert ("road", "a", "b") in ds
    assert ("at", "b") not in ds
    assert len(ds) == 2
    assert set(ds) == {("at", "a"), ("road", "a", "b")}
    assert ds.atoms == frozenset({("at", "a"), ("road", "a", "b")})


def test_applicable_at_start_true():
    dp = _dp()
    ds = DurativeState.from_problem(dp)
    assert ds.applicable(_grounded(dp, **{"?from": "a", "?to": "b"})) is True


def test_applicable_at_start_false_missing_positive():
    dp = _dp()
    ds = DurativeState.from_problem(dp)
    # go b->a needs (at b) at start, which the init lacks.
    assert ds.applicable(_grounded(dp, **{"?from": "b", "?to": "a"})) is False


def test_applicable_blocked_by_negative_start_condition():
    da = DurativeAction("neg")
    da.duration = 1.0
    da.condition_neg["start"] = {("at", "a")}
    assert DurativeState({("at", "a")}).applicable(da) is False
    assert DurativeState(set()).applicable(da) is True


def test_applicable_ignores_over_and_end():
    # An action whose only over/end conditions are unmet is still start-applicable.
    da = DurativeAction("oe")
    da.duration = 1.0
    da.condition_pos["over"] = {("never", "x")}
    da.condition_pos["end"] = {("never", "y")}
    assert DurativeState(set()).applicable(da) is True


def test_state_normalizes_atom_objects_and_equality():
    a = DurativeState([Atom(["at", "a"])])
    b = DurativeState({("at", "a")})
    assert a == b
    assert hash(a) == hash(b)
    assert a != DurativeState(set())
    assert a != "not-a-state"
    assert repr(a) == "DurativeState([('at', 'a')])"


# -- validation -----------------------------------------------------------
def test_validate_grounded_action_standalone():
    dp = _dp()
    # No declared_predicates -> only duration/parameter checks; must not raise.
    validate_durative_action(_grounded(dp, **{"?from": "a", "?to": "b"}))


def test_validate_full_action_with_predicates():
    validate_durative_action(_synthetic(), {"at", "road", "visited"})


def test_validate_all_durative_actions_ok():
    validate_durative_actions(_dp())  # must not raise


def test_validate_non_durative_domain_is_noop():
    dp = DomainProblem(
        os.path.join(CORPUS, "blocksworld-domain.pddl"),
        os.path.join(CORPUS, "blocksworld-problem.pddl"),
    )
    validate_durative_actions(dp)  # no durative actions -> no-op


def test_validate_missing_duration():
    da = _synthetic(duration=None)
    with pytest.raises(DurativeValidationError, match="no simple numeric duration"):
        validate_durative_action(da)


@pytest.mark.parametrize("bad", [0, -5.0])
def test_validate_non_positive_duration(bad):
    with pytest.raises(DurativeValidationError, match="non-positive duration"):
        validate_durative_action(_synthetic(duration=bad))


def test_validate_undeclared_predicate():
    da = _synthetic()
    da.condition_pos["start"] = {("bogus", "a")}
    with pytest.raises(DurativeValidationError, match="undeclared predicate 'bogus'"):
        validate_durative_action(da, {"at", "road", "visited"})


def test_validate_undeclared_parameter():
    da = DurativeAction("free")
    da.duration = 1.0
    da.variable_list = {"?from": None}
    da.condition_pos["start"] = {Atom(["at", "?to"])}  # ?to not a parameter
    with pytest.raises(DurativeValidationError, match="undeclared parameter '\\?to'"):
        validate_durative_action(da)
