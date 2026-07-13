"""ADL (#10): conditional & universal effects, quantified & full-boolean
preconditions, and object equality — parsed, grounded, evaluated end-to-end.

The two corpus domains are the canonical showcases: ``briefcase`` for
conditional/universal effects and ``rooms`` for a universal precondition plus
equality. The remaining cases pin down each condition/effect node with small
inline domains.
"""
import os

import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import (
    AStarPlanner,
    BFSPlanner,
    GBFSPlanner,
    GroundedTask,
    State,
    UnsupportedRequirementsError,
)
from pddlpy.planning.base import _used_features, validate_requirements

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")
PLANNERS = [BFSPlanner, AStarPlanner, GBFSPlanner]


def _files(name):
    return (os.path.join(CORPUS, "%s-domain.pddl" % name),
            os.path.join(CORPUS, "%s-problem.pddl" % name))


def _dp(name):
    return DomainProblem(*_files(name))


def _inline(tmp_path, domain, problem):
    d = tmp_path / "d.pddl"
    p = tmp_path / "p.pddl"
    d.write_text(domain)
    p.write_text(problem)
    return DomainProblem(str(d), str(p)), str(d), str(p)


def _execute(dp, plan):
    task = GroundedTask(dp)
    state = task.initial
    for action in plan:
        assert state.applicable(action), "inapplicable %r" % (action.operator_name,)
        state = state.apply(action)
    return state, task


# -- corpus: full solve + plan validity -----------------------------------

@pytest.mark.parametrize("planner_cls", PLANNERS)
@pytest.mark.parametrize("name", ["briefcase", "rooms"])
def test_adl_corpus_solves(planner_cls, name):
    dp = _dp(name)
    plan = planner_cls().solve(dp)
    assert plan is not None, "%s found no plan for %s" % (planner_cls.__name__, name)
    final, task = _execute(dp, plan)
    assert task.is_goal(final)


def test_briefcase_optimal_plan():
    plan = BFSPlanner().solve(_dp("briefcase"))
    assert [a.operator_name for a in plan] == ["put-in", "move"]


def test_rooms_optimal_length():
    # clean r1, move, clean r2, declare-done
    assert len(BFSPlanner().solve(_dp("rooms"))) == 4


# -- conditional / universal effect semantics -----------------------------

def _action(task, name, **binding):
    return next(a for a in task.actions
                if a.operator_name == name
                and all(a.variable_list[k] == v for k, v in binding.items()))


def test_conditional_effect_moves_only_contained_items():
    dp = _dp("briefcase")
    task = GroundedTask(dp)
    state = task.initial.apply(_action(task, "put-in", **{"?i": "o1"}))
    state = state.apply(_action(task, "move", **{"?from": "home", "?to": "office"}))
    assert ("at", "o1", "office") in state       # o1 was inside -> moved
    assert ("at", "o1", "home") not in state
    assert ("at", "o2", "home") in state         # o2 was not inside -> stays
    assert ("at", "o2", "office") not in state


def test_universal_effect_moves_all_contained_items():
    dp = _dp("briefcase")
    task = GroundedTask(dp)
    state = task.initial
    state = state.apply(_action(task, "put-in", **{"?i": "o1"}))
    state = state.apply(_action(task, "put-in", **{"?i": "o2"}))
    state = state.apply(_action(task, "move", **{"?from": "home", "?to": "office"}))
    assert ("at", "o1", "office") in state
    assert ("at", "o2", "office") in state


# -- quantified precondition ----------------------------------------------

def test_forall_precondition_gates_action():
    dp = _dp("rooms")
    task = GroundedTask(dp)
    declare = _action(task, "declare-done")
    assert not task.initial.applicable(declare)          # nothing clean yet
    assert declare.precondition is not None
    all_clean = State([("clean", "r1"), ("clean", "r2"), ("robot-in", "r1")])
    assert all_clean.applicable(declare)                 # forall satisfied
    one_clean = State([("clean", "r1"), ("robot-in", "r1")])
    assert not one_clean.applicable(declare)


# -- equality --------------------------------------------------------------

def test_equality_excludes_identity_binding():
    dp = _dp("rooms")
    state = State([("robot-in", "r1")])
    applicable = [m for m in dp.ground_operator("move") if state.applicable(m)]
    assert applicable
    assert all(m.variable_list["?from"] != m.variable_list["?to"] for m in applicable)
    assert any(m.variable_list == {"?from": "r1", "?to": "r2"} for m in applicable)


def test_equality_true_branch(tmp_path):
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain eq) (:requirements :equality)\n"
        " (:predicates (p ?x))\n"
        " (:action a :parameters (?x ?y) :precondition (= ?x ?y) :effect (p ?x)))",
        "(define (problem e) (:domain eq) (:objects o1 o2) (:init) (:goal (p o1)))",
    )
    task = GroundedTask(dp)
    applicable = [a for a in task.actions if task.initial.applicable(a)]
    assert applicable
    assert all(a.variable_list["?x"] == a.variable_list["?y"] for a in applicable)


# -- disjunction / implication --------------------------------------------

def test_or_precondition(tmp_path):
    dp, dfile, pfile = _inline(
        tmp_path,
        "(define (domain d) (:requirements :strips :disjunctive-preconditions)\n"
        " (:predicates (p ?x) (q ?x) (done ?x))\n"
        " (:action a :parameters (?x) :precondition (or (p ?x) (q ?x))"
        " :effect (done ?x)))",
        "(define (problem pr) (:domain d) (:objects o1 o2 o3)\n"
        " (:init (p o1) (q o2)) (:goal (and (done o1) (done o2))))",
    )
    plan = BFSPlanner().solve(dp)
    assert plan is not None and len(plan) == 2
    task = GroundedTask(dp)
    # o3 satisfies neither disjunct -> the Or is false -> inapplicable.
    assert not task.initial.applicable(_action(task, "a", **{"?x": "o3"}))
    assert "or" in repr(_action(task, "a", **{"?x": "o1"}).precondition)
    assert diagnose(dfile, pfile)["valid"]


def test_imply_precondition(tmp_path):
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain d)"
        " (:requirements :disjunctive-preconditions :negative-preconditions)\n"
        " (:predicates (p ?x) (q ?x) (ok ?x))\n"
        " (:action a :parameters (?x) :precondition (imply (p ?x) (q ?x))"
        " :effect (ok ?x)))",
        "(define (problem pr) (:domain d) (:objects o1 o2)\n"
        " (:init (q o1)) (:goal (and (ok o1) (ok o2))))",
    )
    # o1: q holds; o2: p false so (imply p q) is vacuously true. Both apply.
    plan = BFSPlanner().solve(dp)
    assert plan is not None and len(plan) == 2


# -- existential precondition ---------------------------------------------

_EXISTS_DOMAIN = (
    "(define (domain d) (:requirements :typing :existential-preconditions)\n"
    " (:types t)\n"
    " (:predicates (p ?x - t) (ok))\n"
    " (:action a :parameters () :precondition (exists (?x - t) (p ?x))"
    " :effect (ok)))"
)


def test_exists_precondition_true(tmp_path):
    dp, dfile, pfile = _inline(
        tmp_path, _EXISTS_DOMAIN,
        "(define (problem pr) (:domain d) (:objects o1 o2 - t)"
        " (:init (p o2)) (:goal (ok)))",
    )
    plan = BFSPlanner().solve(dp)
    assert plan is not None and len(plan) == 1
    assert diagnose(dfile, pfile)["valid"]


def test_exists_precondition_false_is_unsolvable(tmp_path):
    dp, _, _ = _inline(
        tmp_path, _EXISTS_DOMAIN,
        "(define (problem pr) (:domain d) (:objects o1 o2 - t)"
        " (:init) (:goal (ok)))",
    )
    # No witness for the exists and nothing establishes one -> no plan.
    assert BFSPlanner().solve(dp) is None


def test_untyped_quantifier_variable(tmp_path):
    # A forall with an *untyped* bound variable ranges over every object.
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain d) (:requirements :universal-preconditions)\n"
        " (:predicates (p ?x) (ok))\n"
        " (:action a :parameters () :precondition (forall (?x) (p ?x))"
        " :effect (ok)))",
        "(define (problem pr) (:domain d) (:objects o1 o2)"
        " (:init (p o1) (p o2)) (:goal (ok)))",
    )
    plan = BFSPlanner().solve(dp)
    assert plan is not None and len(plan) == 1


def test_quantifier_over_empty_domain(tmp_path):
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain d)"
        " (:requirements :typing :universal-preconditions"
        " :existential-preconditions)\n"
        " (:types thing widget)\n"
        " (:predicates (p ?x - widget) (ok) (bad))\n"
        " (:action a :parameters () :precondition (forall (?x - widget) (p ?x))"
        " :effect (ok))\n"
        " (:action b :parameters () :precondition (exists (?x - widget) (p ?x))"
        " :effect (bad)))",
        "(define (problem pr) (:domain d) (:objects t1 - thing)"
        " (:init) (:goal (ok)))",
    )
    task = GroundedTask(dp)
    # No widget objects: forall is vacuously true, exists is vacuously false.
    assert task.initial.applicable(_action(task, "a"))
    assert not task.initial.applicable(_action(task, "b"))
    assert BFSPlanner().solve(dp) is not None


# -- conditional-effect edge shapes ---------------------------------------

def test_single_effect_when_and_universal_add(tmp_path):
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain d) (:requirements :typing :conditional-effects)\n"
        " (:types t)\n"
        " (:predicates (flag ?x - t) (marked ?x - t) (touched ?x - t))\n"
        " (:action a :parameters (?x - t) :precondition (flag ?x)\n"
        "   :effect (when (flag ?x) (marked ?x)))\n"
        " (:action b :parameters () :precondition ()\n"
        "   :effect (forall (?x - t) (touched ?x))))",
        "(define (problem pr) (:domain d) (:objects o1 o2 - t)\n"
        " (:init (flag o1))"
        " (:goal (and (marked o1) (touched o1) (touched o2))))",
    )
    final, task = _execute(dp, BFSPlanner().solve(dp))
    assert task.is_goal(final)
    # action b has an empty precondition -> the legacy (tree-less) applicability
    # path is exercised, and its universal effect touches every item.
    assert ("touched", "o1") in final and ("touched", "o2") in final


def test_conditional_numeric_effect(tmp_path):
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain d) (:requirements :conditional-effects :numeric-fluents)\n"
        " (:predicates (flag) (go))\n"
        " (:functions (n))\n"
        " (:action a :parameters () :precondition (go)\n"
        "   :effect (when (flag) (increase (n) 5))))",
        "(define (problem pr) (:domain d)"
        " (:init (flag) (go) (= (n) 0)) (:goal (go)))",
    )
    task = GroundedTask(dp)
    a = _action(task, "a")
    fired = task.initial.apply(a)
    assert fired.fluents[("n",)] == 5.0                       # flag holds -> +5
    not_fired = State([("go",)], {("n",): 0.0}).apply(a)
    assert not_fired.fluents.get(("n",), 0.0) == 0.0          # flag absent -> no change


# -- requirements (#9) + capability negotiation ---------------------------

def test_adl_features_detected():
    assert "conditional-effects" in _used_features(_dp("briefcase"))
    rooms = _used_features(_dp("rooms"))
    assert {"universal-preconditions", "equality", "negative-preconditions"} <= rooms


def test_undeclared_conditional_effect_rejected(tmp_path):
    dp, _, _ = _inline(
        tmp_path,
        "(define (domain d) (:requirements :strips)\n"
        " (:predicates (p) (q))\n"
        " (:action a :parameters () :precondition (p) :effect (when (p) (q))))",
        "(define (problem pr) (:domain d) (:init (p)) (:goal (q)))",
    )
    with pytest.raises(UnsupportedRequirementsError):
        validate_requirements(dp)


def test_planners_accept_adl():
    for name in ("briefcase", "rooms"):
        BFSPlanner().check_capabilities(_dp(name))  # no raise


# -- diagnostics + repr walk the new node types ---------------------------

@pytest.mark.parametrize("name", ["briefcase", "rooms", "numeric-transport"])
def test_diagnose_adl_domains_clean(name):
    result = diagnose(*_files(name))
    assert result["valid"], result


def test_simple_conjunction_flags():
    assert _dp("blocksworld").domain.operators["pick-up"].simple_conjunction
    assert _dp("briefcase").domain.operators["put-in"].simple_conjunction
    assert _dp("rooms").domain.operators["clean-room"].simple_conjunction  # and + not-lit
    assert not _dp("rooms").domain.operators["move"].simple_conjunction    # not (= ..)
    assert not _dp("rooms").domain.operators["declare-done"].simple_conjunction  # forall


def test_legacy_conjunctive_fallback():
    # An Operator built by hand (no precondition tree) still evaluates via the
    # legacy STRIPS conjunctive path in State.applicable.
    from pddlpy.pddl import Operator

    op = Operator("x")
    op.precondition_pos = {("p", "a")}
    assert not State([("q", "a")]).applicable(op)   # missing positive -> False
    assert State([("p", "a")]).applicable(op)


def test_precondition_repr():
    move = next(m for m in _dp("rooms").ground_operator("move")
                if m.variable_list == {"?from": "r1", "?to": "r2"})
    text = repr(move.precondition)
    assert "and" in text and "not" in text and "=" in text and "robot-in" in text
    drive = next(_dp("numeric-transport").ground_operator("drive"))
    assert "fuel" in repr(drive.precondition)  # includes the numeric comparison node
