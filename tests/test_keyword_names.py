"""#163: a name spelled like a grammar keyword (or, and, start, ...) is a
name wherever a name can appear; it used to be a syntax error that also
dropped the rest of :objects."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import atom_tuple, get

DOMAIN = ("(define (domain d) (:requirements :typing) (:types %s)"
          " (:predicates (p ?x - %s) (q ?x - %s))"
          " (:action go :parameters (?x - %s) :precondition (p ?x) :effect (q ?x)))")
PROBLEM = "(define (problem q) (:domain d) (:objects a %s b - %s) (:init (p %s)) (:goal (q %s)))"


@pytest.mark.parametrize("word", ["or", "OR", "and", "not", "imply", "exists", "forall",
                                  "when", "either", "define", "domain", "problem", "number",
                                  "start", "end", "all", "increase", "minimize", "at",
                                  "total-time", "preference", "within"])
def test_keyword_spelled_names(tmp_path, word):
    w = word.lower()
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN % ((word,) * 4))
    p.write_text(PROBLEM % ((word,) * 4))
    dp = DomainProblem(str(d), str(p))
    assert dp.syntax_errors == 0
    assert dp.worldobjects() == {"a": w, w: w, "b": w}
    assert {atom_tuple(a) for a in dp.initialstate()} == {("p", w)}
    assert diagnose(str(d), str(p))["valid"]
    assert len(get("bfs").solve(dp)) == 1


def test_keywords_still_parse_as_keywords(tmp_path):
    """(and), (not ...) and (or ...) keep one reading: predicates can't be
    named like keywords."""
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text("(define (domain d) (:requirements :adl) (:predicates (p ?x) (q ?x))"
                 " (:action go :parameters (?x) :precondition (and (or (p ?x) (q ?x)) (not (q ?x)))"
                 "  :effect (q ?x)))")
    p.write_text("(define (problem q) (:domain d) (:objects or) (:init (p or)) (:goal (and (q or))))")
    dp = DomainProblem(str(d), str(p))
    assert dp.syntax_errors == 0
    assert len(get("bfs").solve(dp)) == 1
