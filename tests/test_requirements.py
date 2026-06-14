"""Model exposes declared :requirements (foundation for #9 + capability
negotiation)."""
import os

from pddlpy import DomainProblem

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(name):
    return DomainProblem(
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


def test_strips_only():
    assert _dp("blocksworld").requirements() == {":strips"}


def test_typing():
    assert _dp("gripper").requirements() == {":strips", ":typing"}


def test_uppercase_requirements_normalized(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:REQUIREMENTS :STRIPS :TYPING)\n"
        " (:types t) (:predicates (p ?x - t))\n"
        " (:action a :parameters (?x - t) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o - t) (:init (p o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    assert dp.requirements() == {":strips", ":typing"}
