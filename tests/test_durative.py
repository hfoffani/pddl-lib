"""#23 durative actions: parsing into the DurativeAction model, time-tagged
conditions/effects, grounding, and __str__.

Note: the reference planners do not cover temporal planning (PRD §4/§8
documents this as out of scope); these tests exercise the object model.
"""
import os

from pddlpy import DomainProblem

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _da():
    return DomainProblem(
        os.path.join(CORPUS, "durative-action-domain.pddl"),
        os.path.join(CORPUS, "durative-action-problem.pddl"),
    )


def test_durative_operator_listed_separately():
    dp = _da()
    assert set(dp.durative_operators()) == {"go"}
    assert set(dp.operators()) == set()  # not an instantaneous action


def test_duration_and_time_tagged_conditions():
    dp = _da()
    go = dp.domain.durative_operators["go"]
    assert go.duration == 5.0

    def tuples(atoms):
        return {tuple(a.predicate) for a in atoms}

    assert tuples(go.condition_pos["start"]) == {("at", "?from")}
    assert tuples(go.condition_pos["over"]) == {("road", "?from", "?to")}
    assert tuples(go.condition_pos["end"]) == {("road", "?from", "?to")}


def test_time_tagged_effects():
    dp = _da()
    go = dp.domain.durative_operators["go"]

    def tuples(atoms):
        return {tuple(a.predicate) for a in atoms}

    assert tuples(go.effect_neg["start"]) == {("at", "?from")}
    assert tuples(go.effect_pos["end"]) == {("at", "?to"), ("visited", "?to")}


def test_grounding_durative():
    dp = _da()
    grounded = list(dp.ground_durative_operator("go"))
    go_ab = next(
        g for g in grounded if g.variable_list == {"?from": "a", "?to": "b"}
    )
    assert go_ab.duration == 5.0
    assert go_ab.condition_pos["start"] == {("at", "a")}
    assert go_ab.condition_pos["over"] == {("road", "a", "b")}
    assert go_ab.effect_pos["end"] == {("at", "b"), ("visited", "b")}
    assert go_ab.effect_neg["start"] == {("at", "a")}


def test_durative_str():
    dp = _da()
    text = str(dp.domain.durative_operators["go"])
    assert "Durative Action: go" in text
    assert "Duration: 5.0" in text
