"""#13 regression: a disjunctive (or ...) precondition must be
distinguishable from a conjunctive (and ...) one. Phase 0 preserves the
top-level connective; full and/or/not tree evaluation is deferred (#10).
"""
from pddlpy import DomainProblem

DOMAIN_TMPL = """(define (domain d)
 (:requirements :strips :disjunctive-preconditions)
 (:predicates (p ?x) (q ?x))
 (:action a :parameters (?x)
   :precondition (%s (p ?x) (q ?x))
   :effect (not (p ?x))))"""

PROBLEM = "(define (problem p) (:domain d) (:objects o) (:init (p o)) (:goal (p o)))"


def _domprob(tmp_path, connective):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(DOMAIN_TMPL % connective)
    problem.write_text(PROBLEM)
    return DomainProblem(str(domain), str(problem))


def test_or_precondition_marked_or(tmp_path):
    dp = _domprob(tmp_path, "or")
    assert dp.domain.operators["a"].precondition_connective == "or"


def test_and_precondition_marked_and(tmp_path):
    dp = _domprob(tmp_path, "and")
    assert dp.domain.operators["a"].precondition_connective == "and"


def test_single_atom_defaults_to_and(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips) (:predicates (p ?x))\n"
        " (:action a :parameters (?x) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(PROBLEM)
    dp = DomainProblem(str(domain), str(problem))
    assert dp.domain.operators["a"].precondition_connective == "and"


def test_connective_propagates_to_grounded(tmp_path):
    dp = _domprob(tmp_path, "or")
    gop = next(dp.ground_operator("a"))
    assert gop.precondition_connective == "or"
