"""#22 type super-sets: the declared :types hierarchy is captured, a parameter
typed with a supertype binds objects of any (transitive) subtype, and the
hierarchy is exposed via the API.
"""
import os

from pddlpy import DomainProblem
from pddlpy.planning import BFSPlanner, GroundedTask

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(name):
    return DomainProblem(
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


# -- hierarchy is captured & exposed ------------------------------------------

def test_type_map_captured():
    dp = _dp("logistics")
    assert dp.types() == {
        "truck": "vehicle",
        "airplane": "vehicle",
        "package": "physobj",
        "vehicle": "physobj",
        "airport": "location",
        "city": "object",
        "location": "object",
        "physobj": "object",
    }


def test_subtypes_of_transitive():
    dp = _dp("logistics")
    assert dp.subtypes_of("object") == {
        "truck", "airplane", "package", "vehicle",
        "airport", "city", "location", "physobj",
    }
    assert dp.subtypes_of("physobj") == {"truck", "airplane", "package", "vehicle"}
    assert dp.subtypes_of("vehicle") == {"truck", "airplane"}
    assert dp.subtypes_of("location") == {"airport"}


def test_subtypes_of_leaf_and_unknown():
    dp = _dp("logistics")
    assert dp.subtypes_of("truck") == set()   # leaf type
    assert dp.subtypes_of("nonsuch") == set()  # undeclared type


# -- supertype parameters bind subtype objects (the core fix) -----------------

def test_supertype_param_binds_subtype_objects():
    dp = _dp("logistics")
    grounds = list(dp.ground_operator("drive-truck"))
    # ?loc-from / ?loc-to are typed `location`; objects are airports + locations.
    locs = {op.variable_list["?loc-from"] for op in grounds}
    assert locs == {"apt1", "apt2", "pos1", "pos2"}
    # full cartesian: 2 trucks * 4 locs * 4 locs * 2 cities
    assert len(grounds) == 64


def test_logistics_solvable_end_to_end():
    # Previously impossible: a `location` parameter never bound `airport`
    # objects, so the operators ground to nothing (the CLAUDE.md Known Issue).
    dp = _dp("logistics")
    plan = BFSPlanner().solve(dp)
    assert plan is not None and len(plan) > 0
    task = GroundedTask(dp)
    state = task.initial
    for action in plan:
        assert state.applicable(action)
        state = state.apply(action)
    assert task.is_goal(state)


def test_bartender_hierarchy_grounds(tmp_path):
    # The multi-level hierarchy from issue #22.
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain bar)\n"
        " (:requirements :strips :typing)\n"
        " (:types ingredient cocktail - beverage\n"
        "         shot shaker - container\n"
        "         beverage container - object)\n"
        " (:predicates (holds ?c - container ?b - beverage) (clean ?c - container))\n"
        " (:action pour :parameters (?c - container ?b - beverage)\n"
        "   :precondition (clean ?c) :effect (holds ?c ?b)))\n"
    )
    problem.write_text(
        "(define (problem p) (:domain bar)\n"
        " (:objects sh1 - shot shk1 - shaker rum - ingredient mojito - cocktail)\n"
        " (:init (clean sh1) (clean shk1))\n"
        " (:goal (and (holds sh1 rum))))\n"
    )
    dp = DomainProblem(str(domain), str(problem))
    grounds = list(dp.ground_operator("pour"))
    containers = {op.variable_list["?c"] for op in grounds}
    beverages = {op.variable_list["?b"] for op in grounds}
    assert containers == {"sh1", "shk1"}            # both container subtypes
    assert beverages == {"rum", "mojito"}           # both beverage subtypes
    assert len(grounds) == 4


# -- regressions: flat-typed and untyped grounding must not change ------------

def test_flat_typing_unchanged():
    dp = _dp("gripper")
    # gripper's `move` over rooms still grounds to the same non-empty set.
    grounds = list(dp.ground_operator("move"))
    assert len(grounds) > 0


def test_untyped_grounding_unchanged(tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain d) (:requirements :strips) (:predicates (p ?x))\n"
        " (:action a :parameters (?x) :precondition (p ?x) :effect (not (p ?x))))"
    )
    problem.write_text(
        "(define (problem p) (:domain d) (:objects o1 o2)\n"
        " (:init (p o1) (p o2)) (:goal (and (p o1))))"
    )
    dp = DomainProblem(str(domain), str(problem))
    grounds = list(dp.ground_operator("a"))
    # Untyped param binds the untyped objects exactly as before (the parser also
    # surfaces atom symbols as untyped objects, a pre-existing quirk; the point
    # here is that o1/o2 still bind and nothing typed leaks in).
    assert {"o1", "o2"} <= {op.variable_list["?x"] for op in grounds}


# -- _is_subtype edge cases ---------------------------------------------------

def test_is_subtype_edges():
    dp = _dp("logistics")
    assert dp._is_subtype("truck", "truck") is True       # equal
    assert dp._is_subtype("truck", "physobj") is True      # transitive
    assert dp._is_subtype("truck", "object") is True       # to root
    assert dp._is_subtype("truck", "location") is False    # unrelated branch
    assert dp._is_subtype(None, None) is True              # untyped param/object
    assert dp._is_subtype(None, "object") is False         # untyped object, typed param
    assert dp._is_subtype("airport", None) is False        # typed object, untyped param


def test_is_subtype_cycle_terminates():
    dp = _dp("logistics")
    # A malformed cyclic hierarchy must not loop forever.
    dp.domain.types = {"a": "b", "b": "a"}
    assert dp._is_subtype("a", "z") is False
