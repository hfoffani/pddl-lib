"""Coverage-driven tests for the object model (pddlpy/pddl.py).

These exercise model paths not touched by the canonical corpus: domain
constants, negative preconditions, and Operator.__str__.
"""
from pddlpy import DomainProblem

DOMAIN = """(define (domain cdom)
 (:requirements :strips :negative-preconditions)
 (:constants c1 c2)
 (:predicates (p ?x) (q ?x))
 (:action a :parameters (?x)
   :precondition (not (p ?x))
   :effect (and (p ?x) (not (q ?x)))))"""

PROBLEM = """(define (problem cprob) (:domain cdom)
 (:objects o1)
 (:init (q o1)) (:goal (p o1)))"""


def _domprob(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(DOMAIN)
    problem.write_text(PROBLEM)
    return DomainProblem(str(domain), str(problem))


def test_constants_become_world_objects(tmp_path):
    dp = _domprob(tmp_path)
    objs = dp.worldobjects()
    assert "c1" in objs and "c2" in objs


def test_negative_precondition(tmp_path):
    dp = _domprob(tmp_path)
    op = dp.domain.operators["a"]
    # precondition_pos/neg hold Atom objects without value equality (#21),
    # so compare via their predicate tuples.
    neg = {tuple(a.predicate) for a in op.precondition_neg}
    pos = {tuple(a.predicate) for a in op.precondition_pos}
    eff_neg = {tuple(a.predicate) for a in op.effect_neg}
    assert ("p", "?x") in neg
    assert ("p", "?x") not in pos
    assert ("q", "?x") in eff_neg


def test_operator_str(tmp_path):
    dp = _domprob(tmp_path)
    text = str(dp.domain.operators["a"])
    assert "Operator Name: a" in text
    assert "Precondition Connective: and" in text
    assert "Negative Preconditions" in text
