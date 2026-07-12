"""PDDL diagnostics (#94): diagnose() flags what an agent must fix."""
import os

import pytest

from pddlpy.diagnostics import diagnose

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _files(name):
    return (
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


@pytest.fixture
def w(tmp_path):
    def write(name, text):
        p = tmp_path / name
        p.write_text(text)
        return str(p)
    return write


GOOD_PROBLEM = "(define (problem t) (:domain toy) (:objects o1) (:init (p o1)) (:goal (r o1)))"


def _checks(report):
    return [(i["severity"], i["check"]) for i in report["issues"]]


def test_clean_pair_is_valid():
    report = diagnose(*_files("blocksworld"))
    assert report == {"valid": True, "issues": []}


def test_clean_durative_pair_is_valid():
    assert diagnose(*_files("durative-action"))["valid"] is True


def test_syntax_error_short_circuits(w):
    dom = w("d.pddl", "(define (domain toy) (:predicates (p))"
                      " (:action a :parameters () :precondition (p) :effect (p))")
    prob = w("p.pddl", "(define (problem t) (:domain toy) (:init (p)) (:goal (p)))")
    report = diagnose(dom, prob)
    assert report["valid"] is False
    assert _checks(report) == [("error", "syntax")]
    assert "domain file: line 1:" in report["issues"][0]["message"]


def test_undeclared_predicate(w):
    dom = w("d.pddl", "(define (domain toy) (:predicates (p ?x))"
                      " (:action a :parameters (?x) :precondition (p ?x) :effect (r ?x)))")
    prob = w("p.pddl", "(define (problem t) (:domain toy) (:objects o1)"
                       " (:init (p o1)) (:goal (p o1)))")
    report = diagnose(dom, prob)
    assert report["valid"] is False
    assert ("error", "undeclared_predicate") in _checks(report)
    assert "'r'" in report["issues"][0]["message"]
    assert "action 'a'" in report["issues"][0]["message"]


def test_unknown_object_in_goal(w):
    dom = w("d.pddl", "(define (domain toy) (:predicates (p ?x))"
                      " (:action a :parameters (?x) :precondition (p ?x) :effect (p ?x)))")
    prob = w("p.pddl", "(define (problem t) (:domain toy) (:objects o1)"
                       " (:init (p o1)) (:goal (p zz)))")
    report = diagnose(dom, prob)
    assert report["valid"] is False
    assert ("error", "unknown_object") in _checks(report)
    assert "'zz'" in report["issues"][0]["message"] and ":goal" in report["issues"][0]["message"]


def test_zero_groundings_is_warning_only(w):
    dom = w("d.pddl", "(define (domain toy) (:predicates (p ?x) (q ?x) (r ?x))"
                      " (:action a :parameters (?x)"
                      " :precondition (and (p ?x) (q ?x)) :effect (r ?x)))")
    prob = w("p.pddl", GOOD_PROBLEM)  # no (q _) fact in :init
    report = diagnose(dom, prob)
    assert _checks(report) == [("warning", "zero_groundings")]
    assert report["valid"] is True  # warning does not invalidate
    assert "'a'" in report["issues"][0]["message"]


def test_broken_durative_action(w):
    dom = w("d.pddl", "(define (domain toy) (:requirements :durative-actions)"
                      " (:predicates (p ?x))"
                      " (:durative-action go :parameters (?x)"
                      "  :duration (= ?duration 0)"
                      "  :condition (and (at start (p ?x)))"
                      "  :effect (and (at end (p ?x)))))")
    prob = w("p.pddl", "(define (problem t) (:domain toy) (:objects o1)"
                       " (:init (p o1)) (:goal (p o1)))")
    report = diagnose(dom, prob)
    assert report["valid"] is False
    assert ("error", "durative") in _checks(report)
    assert "non-positive duration" in str(report["issues"])


def test_domain_without_predicates_skips_declaration_check(w):
    dom = w("d.pddl", "(define (domain toy)"
                      " (:action a :parameters (?x) :precondition (p ?x) :effect (p ?x)))")
    prob = w("p.pddl", "(define (problem t) (:domain toy) (:objects o1)"
                       " (:init (p o1)) (:goal (p o1)))")
    report = diagnose(dom, prob)
    assert ("error", "undeclared_predicate") not in _checks(report)
