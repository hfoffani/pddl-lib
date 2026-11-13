"""#141 stopgap: the parser recovers from a syntax error by skipping what it
cannot read, e.g. (:derived ...) before it parsed, or a requirement key the
grammar doesn't know. Solving the rest answers for a different domain, so
solve refuses any pair with syntax errors, as plan validation already did."""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.cli import main
from pddlpy.diagnostics import diagnose
from pddlpy.planning import UnsupportedRequirementsError, get

DOMAIN = ("(define (domain t) (:requirements :strips :object-fluents)"
          " (:predicates (p ?x) (q ?x))"
          " (:action go :parameters (?x) :precondition (p ?x) :effect (q ?x)))")
PROBLEM = "(define (problem p) (:domain t) (:objects a) (:init (p a)) (:goal (q a)))"


@pytest.fixture
def pair(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM)
    return str(d), str(p)


@pytest.mark.parametrize("planner", ["bfs", "astar", "temporal"])
def test_solve_refuses_syntax_errors(pair, planner):
    dp = DomainProblem(*pair)
    assert dp.syntax_errors
    with pytest.raises(UnsupportedRequirementsError, match="syntax errors.*#141"):
        get(planner).solve(dp)


def test_cli_solve_exits_2(pair, capsys):
    assert main(["solve", *pair]) == 2


def test_validate_reports_syntax_only(pair):
    checks = {i["check"] for i in diagnose(*pair)["issues"]}
    assert "syntax" in checks and "unsupported" not in checks


IPC = os.path.join(os.path.dirname(__file__), "corpus", "ipc")


@pytest.mark.parametrize("name", ["openstacks-net-benefit-optimal-adl", "tpp-preferences-simple"])
def test_recovered_tree_loads_partially(name):
    """A tree ANTLR recovered from syntax errors can lack children the
    listener expects; the load stops there instead of crashing."""
    dp = DomainProblem("%s/%s/domain.pddl" % (IPC, name), "%s/%s/p01.pddl" % (IPC, name))
    assert dp.syntax_errors and dp.domain.predicates


def test_listener_bug_without_syntax_errors_propagates(pair, monkeypatch, tmp_path):
    from pddlpy.pddl import DomainListener

    def boom(self, ctx):
        raise RuntimeError("listener bug")
    monkeypatch.setattr(DomainListener, "enterPredicatesDef", boom)
    d = tmp_path / "ok.pddl"
    d.write_text("(define (domain t) (:predicates (p ?x)))")
    with pytest.raises(RuntimeError, match="listener bug"):
        DomainProblem(str(d), pair[1])
