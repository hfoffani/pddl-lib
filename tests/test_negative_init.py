"""#186: (not (p a)) in :init is false under the closed-world assumption.
It must not reach the initial state as (p a); validate warns that it is
ignored, and reports an error when the same atom is also asserted."""
from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import atom_tuple, get

DOMAIN = ("(define (domain t) (:predicates (p ?x) (q ?x))"
          " (:action go :parameters (?x) :precondition (p ?x) :effect (q ?x)))")


def _pair(tmp_path, init):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text("(define (problem p) (:domain t) (:objects a b)"
                 " (:init %s) (:goal (q a)))" % init)
    return str(d), str(p)


def _issues(d, p):
    return [(i["severity"], i["message"]) for i in diagnose(d, p)["issues"]
            if i["check"] == "negative_init"]


def test_negated_init_literal_is_not_asserted(tmp_path):
    d, p = _pair(tmp_path, "(not (p a)) (p b)")
    dp = DomainProblem(d, p)
    assert {atom_tuple(a) for a in dp.initialstate()} == {("p", "b")}
    assert [atom_tuple(a) for a in dp.problem.negative_init] == [("p", "a")]
    assert get("bfs").solve(dp) is None  # (p a) is false: go(a) never applies
    assert _issues(d, p) == [
        ("warning", "(not (p a)) in :init is ignored: atoms not listed are false")]


def test_asserted_and_negated_is_an_error(tmp_path):
    d, p = _pair(tmp_path, "(p a) (not (p a))")
    report = diagnose(d, p)
    assert report["valid"] is False
    assert _issues(d, p) == [("error", "(p a) is both asserted and negated in :init")]


def test_timed_negation_is_a_timed_literal(tmp_path):
    dp = DomainProblem(*_pair(tmp_path, "(p a) (at 3 (not (p a)))"))
    assert {atom_tuple(a) for a in dp.initialstate()} == {("p", "a")}
    assert dp.problem.negative_init == []
    assert [(t, atom_tuple(a), pos) for t, a, pos in dp.problem.timed_literals] == [
        (3.0, ("p", "a"), False)]


def test_declaration_checks_cover_init_literals_kept_out_of_the_state(tmp_path):
    """Review on #188: negated and timed init literals are not in the
    initial state, but must still name declared predicates and objects."""
    for init, check in [("(not (p missing))", "unknown_object"),
                        ("(not (typo a))", "undeclared_predicate"),
                        ("(at 3 (p missing))", "unknown_object"),
                        ("(at 3 (not (typo a)))", "undeclared_predicate")]:
        report = diagnose(*_pair(tmp_path, init))
        assert report["valid"] is False, init
        assert check in {i["check"] for i in report["issues"]}, init
