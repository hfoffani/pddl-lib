"""UTF-8 PDDL files parse (#103): non-ASCII comments must not crash.

ANTLR's FileStream defaults to ASCII, which made a comment like
``; camión`` raise UnicodeDecodeError before parsing started.
"""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import get

DOMAIN = """\
; dominio del camión — mueve paquetes entre sitios ✓
(define (domain reparto)
  (:predicates (en ?x) (meta ?x))
  (:action ir
    :parameters (?x)
    :precondition (en ?x)
    :effect (and (not (en ?x)) (meta ?x))))
"""

PROBLEM = """\
; problema: llegar a la meta — ¡fácil!
(define (problem uno)
  (:domain reparto)
  (:objects sitio)
  (:init (en sitio))
  (:goal (meta sitio)))
"""


@pytest.fixture
def utf8_pair(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(DOMAIN, encoding="utf-8")
    problem.write_text(PROBLEM, encoding="utf-8")
    return str(domain), str(problem)


def test_utf8_comments_parse_and_solve(utf8_pair):
    dp = DomainProblem(*utf8_pair)
    assert list(dp.operators()) == ["ir"]
    plan = get("bfs").solve(dp)
    assert plan is not None and len(plan) == 1


def test_utf8_comments_diagnose_clean(utf8_pair):
    assert diagnose(*utf8_pair) == {"valid": True, "issues": []}
