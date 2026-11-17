"""Quantified variables in durative conditions are not parameters (#193)."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose

DOMAIN = """(define (domain t) (:requirements :typing :adl :durative-actions)
  (:types a)
  (:predicates (p ?x - a) (q ?x - a))
  (:durative-action go :parameters (?x - a) :duration (= ?duration 1)
    :condition %s
    :effect (at end (q ?x))))"""
PROBLEM = "(define (problem p) (:domain t) (:objects o - a) (:init (p o)) (:goal (q o)))"


@pytest.mark.parametrize("condition", [
    "(at start (forall (?y - a) (p ?y)))",
    "(over all (EXISTS (?y - a) (p ?y)))",
    "(and (at start (p ?x)) (at end (forall (?y - a) (not (q ?y)))))",
])
def test_quantified_variable_is_not_undeclared(tmp_path, condition):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % condition)
    p.write_text(PROBLEM)
    dp = DomainProblem(str(d), str(p))
    assert not any("undeclared" in i["message"] for i in diagnose(str(d), str(p))["issues"])
    action = dp.domain.durative_operators["go"]
    assert not action.simple
    atoms = [a for t in action.condition_pos.values() for a in t]
    assert all("?y" not in a.predicate for a in atoms)


def test_free_variable_is_still_undeclared(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % "(at start (p ?y))")
    p.write_text(PROBLEM)
    issues = diagnose(str(d), str(p))["issues"]
    assert any("undeclared parameter '?y'" in i["message"] for i in issues)
