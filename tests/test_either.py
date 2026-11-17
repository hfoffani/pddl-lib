"""``(either ...)`` types bind objects of any member type (#200)."""
from pddlpy import DomainProblem
from pddlpy.planning import get

DOMAIN = """(define (domain e) (:requirements :strips :typing)
  (:types vehicle - object truck plane - vehicle boat cargo - object
          amphibian - (either truck boat) small - amphibian)
  (:predicates (at ?v - (either truck boat)) (moved ?v - object))
  (:action go :parameters (?v - (EITHER truck boat))
    :precondition (at ?v) :effect (moved ?v)))"""
PROBLEM = """(define (problem p) (:domain e)
  (:objects t1 - truck p1 - plane b1 - boat c1 - cargo a1 - amphibian
            x - (either truck cargo) y - (either plane cargo))
  (:init (at t1) (at b1) (at x) (at a1))
  (:goal (and (moved t1) (moved b1) (moved x) (moved a1))))"""


def _dp(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM)
    return DomainProblem(str(d), str(p))


def test_either_parameter_binds_member_types(tmp_path):
    dp = _dp(tmp_path)
    bound = sorted(o.variable_list["?v"] for o in dp.ground_operator("go"))
    # a1's type is a subtype of (either truck boat); x is declared (either truck
    # cargo), so it is a truck; y is neither a truck nor a boat
    assert bound == ["a1", "b1", "t1", "x"]
    assert dp.candidate_objects("(either plane boat)") == ["p1", "b1", "a1", "y"]
    assert dp.types()["amphibian"] == "(either truck boat)"
    assert dp.subtypes_of("truck") == {"amphibian", "small"}
    assert dp.subtypes_of("vehicle") == {"truck", "plane", "amphibian", "small"}
    assert dp.subtypes_of("object") == {"vehicle", "truck", "plane", "boat", "cargo", "amphibian", "small"}


def test_either_domain_solves(tmp_path):
    plan = get("bfs").solve(_dp(tmp_path))
    assert plan is not None and len(plan) == 4


def test_type_cycle_through_either_terminates(tmp_path):
    """A cycle through an (either ...) supertype must not recurse forever."""
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text("(define (domain c) (:requirements :typing)"
                 " (:types a - (either b c) b - a c - object) (:predicates (p ?x - c)))")
    p.write_text("(define (problem p) (:domain c) (:objects x - a) (:init) (:goal (and)))")
    dp = DomainProblem(str(d), str(p))
    assert dp.candidate_objects("c") == ["x"]
    assert dp.candidate_objects("object") == ["x"]
    assert dp.candidate_objects("zzz") == []
