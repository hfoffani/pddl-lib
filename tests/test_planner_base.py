"""Planner ABC, capability negotiation, registry, and #9 enforcement."""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.planning import (
    Planner,
    UnsupportedRequirementsError,
    registry,
    validate_requirements,
)
from pddlpy.planning.base import _used_features

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(name):
    return DomainProblem(
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


def test_planner_is_abstract():
    with pytest.raises(TypeError):
        Planner()  # cannot instantiate the ABC


class _StripsOnly(Planner):
    capabilities = frozenset({":strips"})

    def solve(self, domainproblem):
        return None


class _Typed(Planner):
    capabilities = frozenset({":strips", ":typing"})

    def solve(self, domainproblem):
        return None


def test_capability_negotiation_rejects_unsupported():
    # gripper declares :typing, which the STRIPS-only planner lacks.
    with pytest.raises(UnsupportedRequirementsError):
        _StripsOnly().check_capabilities(_dp("gripper"))


def test_capability_negotiation_accepts_supported():
    _Typed().check_capabilities(_dp("gripper"))  # no raise
    _StripsOnly().check_capabilities(_dp("blocksworld"))  # no raise


def test_used_features_detection():
    assert "typing" in _used_features(_dp("gripper"))
    assert _used_features(_dp("blocksworld")) == set()


def test_requirements_enforcement_typing_undeclared(tmp_path):
    # Uses typing but only declares :strips -> #9 violation.
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips)\n"
        " (:types t) (:predicates (p ?x - t))\n"
        " (:action a :parameters (?x - t) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o - t) (:init (p o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    with pytest.raises(UnsupportedRequirementsError):
        validate_requirements(dp)


def test_requirements_enforcement_passes_for_corpus():
    for name in ("blocksworld", "gripper", "logistics"):
        validate_requirements(_dp(name))  # no raise


def test_requirement_free_domain_is_lenient(tmp_path):
    # No :requirements declared -> enforcement is skipped even with typing.
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d)\n"
        " (:types t) (:predicates (p ?x - t))\n"
        " (:action a :parameters (?x - t) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o - t) (:init (p o)) (:goal (p o)))"
    )
    dp = DomainProblem(str(domain), str(problem))
    validate_requirements(dp)  # no raise


def test_registry_register_and_get():
    registry.register("strips-only", _StripsOnly)
    planner = registry.get("strips-only")
    assert isinstance(planner, _StripsOnly)
    assert "strips-only" in registry.names()


def test_registry_unknown_name():
    with pytest.raises(KeyError):
        registry.get("does-not-exist")
