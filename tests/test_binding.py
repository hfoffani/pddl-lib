"""#12 better variable binding: the default StaticPrunedBinder prunes bindings
that can never be applicable (via static preconditions) while remaining sound,
the CartesianBinder reproduces the full product, and binders are pluggable.
"""
import os

from pddlpy import DomainProblem
from pddlpy.binding import CartesianBinder, StaticPrunedBinder, VariableBinder
from pddlpy.planning import BFSPlanner, GroundedTask

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _dp(name, **kw):
    return DomainProblem(
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
        **kw,
    )


def _binds(grounds):
    return {tuple(sorted(op.variable_list.items())) for op in grounds}


# -- pruning is a sound subset of the cartesian product -----------------------

def test_pruned_is_strict_subset_of_cartesian():
    pruned = list(_dp("logistics").ground_operator("drive-truck"))
    cart = list(_dp("logistics", binder=CartesianBinder()).ground_operator("drive-truck"))
    assert len(pruned) < len(cart)            # actually pruned (16 vs 64)
    assert _binds(pruned) < _binds(cart)      # and a strict subset


def test_dropped_bindings_are_never_applicable():
    # Every cartesian binding the pruner drops is genuinely inapplicable in the
    # initial state — the soundness guarantee.
    dp = _dp("logistics")
    task = GroundedTask(dp)  # grounded with the default pruned binder
    init = task.initial
    pruned = _binds(dp.ground_operator("drive-truck"))
    cart = list(_dp("logistics", binder=CartesianBinder()).ground_operator("drive-truck"))
    dropped = [op for op in cart
               if tuple(sorted(op.variable_list.items())) not in pruned]
    assert dropped
    for op in dropped:
        assert not init.applicable(op)


def test_pruned_and_cartesian_solve_identically():
    for name in ("blocksworld", "gripper", "logistics"):
        pruned_plan = BFSPlanner().solve(_dp(name))
        cart_plan = BFSPlanner().solve(_dp(name, binder=CartesianBinder()))
        assert pruned_plan is not None and cart_plan is not None
        assert len(pruned_plan) == len(cart_plan)


# -- static_predicates --------------------------------------------------------

def test_static_predicates_logistics():
    # in-city never appears in an effect; at/in do.
    assert _dp("logistics").static_predicates() == {"in-city"}


def test_static_predicates_includes_durative_effects():
    # Exercises the durative-effect branch: predicates modified by a durative
    # action are not static.
    dp = DomainProblem(
        os.path.join(CORPUS, "durative-action-domain.pddl"),
        os.path.join(CORPUS, "durative-action-problem.pddl"),
    )
    static = dp.static_predicates()
    modified = set()
    for da in dp.domain.durative_operators.values():
        for t in da.EFFECT_TIMES:
            for a in da.effect_pos[t] | da.effect_neg[t]:
                modified.add(a.predicate[0])
    assert static.isdisjoint(modified)


# -- pluggability -------------------------------------------------------------

def test_custom_binder_is_used():
    calls = []

    class OneBinder(VariableBinder):
        def bind(self, dp, operator):
            calls.append(operator.operator_name)
            yield {v: "x" for v in operator.variable_list}

    dp = _dp("gripper", binder=OneBinder())
    grounds = list(dp.ground_operator("move"))
    assert len(grounds) == 1
    assert calls == ["move"]
    # also settable after construction
    dp2 = _dp("gripper")
    dp2.binder = OneBinder()
    assert len(list(dp2.ground_operator("move"))) == 1


def test_default_binder_is_static_pruned():
    assert isinstance(_dp("gripper").binder, StaticPrunedBinder)


# -- branch coverage on small hand-built domains ------------------------------

def _make(tmp_path, domain_text, problem_text):
    d = tmp_path / "d.pddl"
    p = tmp_path / "p.pddl"
    d.write_text(domain_text)
    p.write_text(problem_text)
    return DomainProblem(str(d), str(p))


def test_disjunctive_precondition_not_pruned(tmp_path):
    # (or ...) falls back to cartesian; q is static and absent from init but the
    # binding is still produced (consuming the full generator covers the return).
    dp = _make(
        tmp_path,
        "(define (domain d) (:requirements :strips :disjunctive-preconditions)\n"
        " (:predicates (p ?x) (q ?x))\n"
        " (:action a :parameters (?x) :precondition (or (p ?x) (q ?x))\n"
        "   :effect (not (p ?x))))",
        "(define (problem p) (:domain d) (:objects o1 o2)\n"
        " (:init (p o1)) (:goal (and (p o1))))",
    )
    grounds = list(dp.ground_operator("a"))
    assert {op.variable_list["?x"] for op in grounds} >= {"o1", "o2"}


def test_unsatisfiable_static_precondition_yields_nothing(tmp_path):
    # s is static and there are no s facts in init -> no grounding can apply.
    dp = _make(
        tmp_path,
        "(define (domain d) (:requirements :strips)\n"
        " (:predicates (s ?x) (done ?x))\n"
        " (:action a :parameters (?x) :precondition (s ?x) :effect (done ?x)))",
        "(define (problem p) (:domain d) (:objects o1 o2)\n"
        " (:init (done o1)) (:goal (and (done o1))))",
    )
    assert list(dp.ground_operator("a")) == []


def test_negative_static_precondition_filters(tmp_path):
    # blocked is static; (not (blocked ?x)) drops o1 but keeps o2.
    dp = _make(
        tmp_path,
        "(define (domain d) (:requirements :strips :negative-preconditions)\n"
        " (:predicates (free ?x) (blocked ?x) (done ?x))\n"
        " (:action a :parameters (?x)\n"
        "   :precondition (and (free ?x) (not (blocked ?x))) :effect (done ?x)))",
        "(define (problem p) (:domain d) (:objects o1 o2)\n"
        " (:init (free o1) (free o2) (blocked o1)) (:goal (and (done o2))))",
    )
    grounds = list(dp.ground_operator("a"))
    assert {op.variable_list["?x"] for op in grounds} == {"o2"}


def test_type_incompatible_init_binding_rejected(tmp_path):
    # holds is static; init applies it to a box, but the parameter is an item,
    # so that join candidate is rejected on the type check.
    dp = _make(
        tmp_path,
        "(define (domain d) (:requirements :strips :typing)\n"
        " (:types item box)\n"
        " (:predicates (holds ?i - item) (modi ?i - item))\n"
        " (:action a :parameters (?i - item) :precondition (holds ?i)\n"
        "   :effect (modi ?i)))",
        "(define (problem p) (:domain d) (:objects it1 - item bx1 - box)\n"
        " (:init (holds it1) (holds bx1)) (:goal (and (modi it1))))",
    )
    grounds = list(dp.ground_operator("a"))
    assert {op.variable_list["?i"] for op in grounds} == {"it1"}


def test_constant_in_static_precondition(tmp_path):
    # at is static and references the constant `home`; only objects at home bind.
    dp = _make(
        tmp_path,
        "(define (domain d) (:requirements :strips :typing)\n"
        " (:types loc obj) (:constants home - loc)\n"
        " (:predicates (at ?o - obj ?l - loc) (moved ?o - obj))\n"
        " (:action a :parameters (?o - obj) :precondition (at ?o home)\n"
        "   :effect (moved ?o)))",
        "(define (problem p) (:domain d) (:objects o1 o2 - obj away - loc)\n"
        " (:init (at o1 home) (at o2 away)) (:goal (and (moved o1))))",
    )
    grounds = list(dp.ground_operator("a"))
    assert {op.variable_list["?o"] for op in grounds} == {"o1"}
