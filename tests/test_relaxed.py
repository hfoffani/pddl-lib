"""Relaxed exploration (pddlpy/planning/relaxed.py): reachable atoms and
actions under the delete relaxation."""
import os

from pddlpy import DomainProblem
from pddlpy.planning import GroundedTask
from pddlpy.planning.relaxed import RelaxedTask, needed_atoms

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")

# a -> b -> c; nothing leads to d, and (lock) is never added.
CHAIN = """(define (domain chain)
 (:requirements :strips :negative-preconditions :disjunctive-preconditions)
 (:predicates (at ?x) (link ?x ?y) (lock) (visited ?x))
 (:action go :parameters (?x ?y)
  :precondition (and (at ?x) (link ?x ?y) (not (visited ?y)))
  :effect (and (at ?y) (visited ?y) (not (at ?x))))
 (:action locked :parameters (?x)
  :precondition (and (at ?x) (lock))
  :effect (visited ?x))
 (:action alt :parameters (?x)
  :precondition (or (at ?x) (lock))
  :effect (visited ?x)))"""


def chain(tmp_path, goal):
    (tmp_path / "d.pddl").write_text(CHAIN)
    (tmp_path / "p.pddl").write_text(
        "(define (problem p) (:domain chain) (:objects a b c d)"
        " (:init (at a) (link a b) (link b c)) (:goal %s))" % goal)
    return RelaxedTask(GroundedTask(DomainProblem(str(tmp_path / "d.pddl"),
                                                  str(tmp_path / "p.pddl"))))


def names(relaxed, indices):
    acts = relaxed.task.actions
    return {(acts[i].operator_name,) + tuple(acts[i].variable_list.values()) for i in indices}


def test_reachable_atoms_and_actions(tmp_path):
    relaxed = chain(tmp_path, "(and (at c) (not (at a)))")
    ex = relaxed.explore()
    assert {a for a in ex.atoms if a[0] == "at"} == {("at", "a"), ("at", "b"), ("at", "c")}
    assert ("lock",) not in ex.atoms
    reached = names(relaxed, ex.actions)
    assert {("go", "a", "b"), ("go", "b", "c")} <= reached
    # (lock) is never added; the disjunction counts as satisfiable
    assert not any(n[0] == "locked" for n in reached)
    assert ("alt", "d") in reached
    assert ex.solvable and ex.goals == frozenset()
    assert relaxed.goal == {("at", "c")}


def test_unreachable_goal_atoms(tmp_path):
    ex = chain(tmp_path, "(and (at d) (at c) (lock))").explore()
    assert not ex.solvable
    assert ex.goals == {("at", "d"), ("lock",)}


def test_explore_from_given_atoms(tmp_path):
    relaxed = chain(tmp_path, "(at c)")
    ex = relaxed.explore([("at", "b"), ("link", "b", "c")])
    assert ("at", "c") in ex.atoms and ("at", "b") in ex.atoms
    assert names(relaxed, ex.actions) >= {("go", "b", "c")}
    assert ("go", "a", "b") not in names(relaxed, ex.actions)
    # from nothing, only the action with no needed atoms applies
    assert relaxed.explore([]).atoms == {("visited", x) for x in "abcd"}


def test_needed_atoms_skips_and_nests():
    from pddlpy.pddl import And, Atom, Lit, Not, Or
    cond = And([Lit(Atom(("p", "a"))), And([Lit(Atom(("q",))), Not(Lit(Atom(("r",))))]),
                Or([Lit(Atom(("s",)))])])
    assert needed_atoms(cond) == {("p", "a"), ("q",)}
    assert needed_atoms(cond, {"q"}) == {("p", "a")}
    assert needed_atoms(None) == set()


def test_conditional_adds_and_no_tree(tmp_path):
    (tmp_path / "d.pddl").write_text("""(define (domain w)
 (:requirements :strips :conditional-effects)
 (:predicates (on) (lit) (dark))
 (:action flip :parameters () :precondition (on)
  :effect (when (dark) (lit))))""")
    (tmp_path / "p.pddl").write_text(
        "(define (problem p) (:domain w) (:init (on)) (:goal (lit)))")
    task = GroundedTask(DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl")))
    relaxed = RelaxedTask(task)
    assert relaxed.add == [frozenset({("lit",)})]
    assert relaxed.explore().solvable
    # an operator built without a precondition tree: the flat atoms count
    task.actions[0].precondition = None
    assert RelaxedTask(task).pre == [frozenset({("on",)})]


def test_derived_atoms_count_as_reached():
    d = os.path.join(CORPUS, "ipc", "psr-middle-derived-predicates-adl")
    task = GroundedTask(DomainProblem(os.path.join(d, "domain.pddl"),
                                      os.path.join(d, "p01.pddl")))
    derived = {r.predicate for r in task.domainproblem.domain.derived}
    relaxed = RelaxedTask(task)
    assert not any(a[0] in derived for pre in relaxed.pre for a in pre)
    assert not any(a[0] in derived for a in relaxed.goal)
    assert relaxed.explore().solvable


def test_blocksworld_reaches_the_goal():
    task = GroundedTask(DomainProblem(os.path.join(CORPUS, "blocksworld-domain.pddl"),
                                      os.path.join(CORPUS, "blocksworld-problem.pddl")))
    ex = RelaxedTask(task).explore()
    assert ex.solvable and len(ex.actions) == len(task.actions)


def test_ff_counts_a_relaxed_plan(tmp_path):
    relaxed = chain(tmp_path, "(and (at c) (visited b))")
    # alt b, which needs nothing, is the first to reach (visited b); then
    # go a b and go b c reach (at c)
    assert relaxed.ff(relaxed.task.initial.atoms) == 3
    assert relaxed.ff([("at", "b"), ("link", "b", "c")]) == 2  # go b c + alt b
    assert relaxed.ff([("at", "c"), ("visited", "b")]) == 0
    assert relaxed.ff([("at", "c")]) == 1  # alt b, which needs nothing
    assert relaxed.ff([("visited", "b")]) is None  # (at c) unreachable


def test_ff_dead_end(tmp_path):
    relaxed = chain(tmp_path, "(lock)")
    assert relaxed.ff(relaxed.task.initial.atoms) is None


def test_gbfs_solves_and_proves(tmp_path):
    from pddlpy.planning import get
    plan = get("gbfs").solve(chain(tmp_path, "(at c)").task.domainproblem)
    assert [a.operator_name for a in plan] == ["go", "go"]
    # the relaxation proves it unsolvable before any search
    assert get("gbfs").solve(chain(tmp_path, "(lock)").task.domainproblem) is None
    # the goal holds at the start
    assert len(get("gbfs").solve(chain(tmp_path, "(at a)").task.domainproblem)) == 0


def test_gbfs_exhausts_what_the_relaxation_misses(tmp_path):
    # (not (visited b)) blocks go a b; the relaxation ignores negative
    # conditions, so only the search proves there is no plan
    (tmp_path / "d.pddl").write_text(CHAIN)
    (tmp_path / "p.pddl").write_text(
        "(define (problem p) (:domain chain) (:objects a b)"
        " (:init (at a) (link a b) (visited b)) (:goal (at b)))")
    from pddlpy.planning import get
    dp = DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))
    assert RelaxedTask(GroundedTask(dp)).explore().solvable
    assert get("gbfs").solve(dp) is None
