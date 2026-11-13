"""Derived predicates, (:derived (p ?x) GD) (#141): recomputed in every
state, recursive rules to a fixpoint, negation by strata."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, State, UnsupportedRequirementsError, atom_tuple, get
from pddlpy.planning.validation import parse_plan, simulate, validate_plan

DOMAIN = ("(define (domain t) (:requirements :strips :derived-predicates :negative-preconditions)"
          " (:predicates (p ?x) (q ?x) (r ?x))"
          " (:derived (r ?x) (and (q ?x) (not (p ?x))))"
          " (:action go :parameters (?x) :precondition (p ?x) :effect (and (q ?x) (not (p ?x)))))")
PROBLEM = "(define (problem p) (:domain t) (:objects a b) (:init (p a)) (:goal (r a)))"

# reachability over edges: a recursive rule, and a negated derived predicate
# in a later stratum
GRAPH = ("(define (domain g) (:requirements :strips :derived-predicates :negative-preconditions)"
         " (:predicates (edge ?x ?y) (reach ?x ?y) (cut ?x) (lonely ?x) (done))"
         " (:derived (reach ?x ?y) (or (edge ?x ?y) (exists (?z) (and (edge ?x ?z) (reach ?z ?y)))))"
         " (:derived (lonely ?x) (not (exists (?y) (reach ?x ?y))))"
         " (:action link :parameters (?x ?y) :precondition (lonely ?x) :effect (edge ?x ?y))"
         " (:action finish :parameters () :precondition (reach a d) :effect (done)))")
GRAPH_PROBLEM = ("(define (problem g) (:domain g) (:objects a b c d)"
                 " (:init (edge b c) (edge c d)) (:goal (done)))")


def _pair(tmp_path, domain=DOMAIN, problem=PROBLEM):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(domain)
    p.write_text(problem)
    return str(d), str(p)


def test_rule_is_parsed(tmp_path):
    dp = DomainProblem(*_pair(tmp_path))
    assert dp.syntax_errors == 0
    (rule,) = dp.domain.derived
    assert rule.predicate == "r" and rule.params == [("?x", None)]
    assert repr(rule) == "(:derived (r ?x) (and ('q', '?x') (not ('p', '?x'))))"
    # the rule's atoms land nowhere else: the action is unchanged
    (go, _) = sorted(dp.ground_operator("go"), key=lambda o: o.variable_list["?x"])
    assert go.precondition_pos == {("p", "a")}
    assert dp.derived_predicates() == {"r"} and "r" not in dp.static_predicates()


@pytest.mark.parametrize("planner", ["bfs", "astar", "gbfs", "ucs"])
def test_derived_goal_is_solved(tmp_path, planner):
    d, p = _pair(tmp_path)
    dp = DomainProblem(d, p)
    plan = get(planner).solve(dp)
    assert plan.action_names() == [("go", {"?x": "a"})]
    assert validate_plan(dp, parse_plan("(go a)\n")).valid
    failure = validate_plan(dp, []).failure
    assert failure.kind == "goal" and failure.unmet == ("(r a)",)
    assert diagnose(d, p)["valid"]


def test_derived_atoms_follow_the_state(tmp_path):
    dp = DomainProblem(*_pair(tmp_path))
    init = State.from_problem(dp)
    assert init.atoms == {("p", "a")}
    # a derived atom put in by hand is recomputed away
    assert State({("p", "a"), ("r", "b")}).derived(dp).atoms == {("p", "a")}
    sim = simulate(dp, parse_plan("(go a)\n"))
    assert sim.state.atoms == {("q", "a"), ("r", "a")}


def test_recursion_and_strata(tmp_path):
    d, p = _pair(tmp_path, GRAPH, GRAPH_PROBLEM)
    dp = DomainProblem(d, p)
    strata = dp.derived_strata()
    assert [[r.predicate for r in s] for s in strata] == [["reach"], ["lonely"]]
    atoms = State.from_problem(dp).atoms
    assert {a for a in atoms if a[0] == "reach"} == {
        ("reach", "b", "c"), ("reach", "c", "d"), ("reach", "b", "d")}
    assert {a[1] for a in atoms if a[0] == "lonely"} == {"a", "d"}
    plan = get("bfs").solve(dp)
    assert [n for n, _ in plan.action_names()] == ["link", "finish"]
    assert validate_plan(dp, parse_plan("(link a b)\n(finish)\n")).valid
    # once a links to b, it is no longer lonely: a second link is refused
    failure = validate_plan(dp, parse_plan("(link a b)\n(link a c)\n")).failure
    assert failure.kind == "precondition" and failure.unmet == ("(lonely a)",)


def test_non_stratifiable_rules_are_refused(tmp_path):
    domain = ("(define (domain n) (:requirements :strips :derived-predicates)"
              " (:predicates (p) (q))"
              " (:derived (p) (not (q))) (:derived (q) (not (p)))"
              " (:action noop :parameters () :effect (and)))")
    d, p = _pair(tmp_path, domain, "(define (problem n) (:domain n) (:init) (:goal (p)))")
    dp = DomainProblem(d, p)
    assert dp.derived_strata() is None
    with pytest.raises(UnsupportedRequirementsError, match="not stratifiable"):
        get("bfs").solve(dp)
    issues = diagnose(d, p)["issues"]
    assert [(i["severity"], i["check"]) for i in issues] == [("error", "unsupported")]


def test_temporal_refuses_derived(tmp_path):
    domain = ("(define (domain t) (:requirements :durative-actions)"
              " (:predicates (p) (r)) (:derived (r) (p))"
              " (:durative-action go :parameters () :duration (= ?duration 1)"
              "  :condition (at start (not (p))) :effect (at end (p))))")
    d, p = _pair(tmp_path, domain, "(define (problem t) (:domain t) (:init) (:goal (r)))")
    with pytest.raises(UnsupportedRequirementsError, match="derived"):
        get("temporal").solve(DomainProblem(d, p))


def test_typed_head_parameters_keep_their_order(tmp_path):
    domain = ("(define (domain y) (:requirements :typing :derived-predicates)"
              " (:types u v) (:predicates (e ?x - u ?y - v) (f ?y - v ?x - u))"
              " (:derived (f ?y - v ?x - u) (e ?x ?y))"
              " (:action noop :parameters () :effect (and)))")
    d, p = _pair(tmp_path, domain, "(define (problem y) (:domain y) (:objects m - u n - v)"
                 " (:init (e m n)) (:goal (f n m)))")
    dp = DomainProblem(d, p)
    assert dp.domain.derived[0].params == [("?y", "v"), ("?x", "u")]
    assert ("f", "n", "m") in State.from_problem(dp).atoms
    assert atom_tuple(next(iter(dp.goals()))) == ("f", "n", "m")


def test_simultaneous_read_through_a_derived_atom_is_mutex(tmp_path):
    """Review on #205: use reads (q), derived from (p), which del deletes in
    the same happening: VAL rejects it; separated, it is valid."""
    domain = ("(define (domain m) (:requirements :strips :derived-predicates :durative-actions)"
              " (:predicates (p) (q) (done)) (:derived (q) (p))"
              " (:action use :parameters () :precondition (q) :effect (done))"
              " (:action del :parameters () :precondition (and) :effect (not (p))))")
    d, p = _pair(tmp_path, domain, "(define (problem m) (:domain m) (:init (p)) (:goal (done)))")
    dp = DomainProblem(d, p)
    failure = validate_plan(dp, parse_plan("0: (use)\n0: (del)\n")).failure
    assert failure.kind == "mutex" and failure.unmet == ("(p)",)
    assert validate_plan(dp, parse_plan("0: (use)\n0.01: (del)\n")).valid
    assert dp.derived_reads({("q",), ("done",)}) == ({("p",)}, set())


def test_derived_reads_are_transitive(tmp_path):
    domain = ("(define (domain r) (:requirements :adl :derived-predicates :numeric-fluents)"
              " (:predicates (p) (q) (s) (z) (r)) (:functions (f))"
              " (:derived (q) (p)) (:derived (s) (q))"
              " (:derived (r) (and (q) (s) (not (z)) (or (z) (<= (f) 1))))"
              " (:action noop :parameters () :effect (and)))")
    d, p = _pair(tmp_path, domain, "(define (problem r) (:domain r) (:init) (:goal (r)))")
    dp = DomainProblem(d, p)
    # (q) is reached twice, through (r) and through (s)
    assert dp.derived_reads({("r",)}) == ({("p",), ("q",), ("s",), ("z",)}, {("f",)})


def test_derived_body_reading_an_undefined_fluent_does_not_hold(tmp_path):
    """Review on #205: (f) has no value, so (q) is not derived until set."""
    domain = ("(define (domain u) (:requirements :strips :derived-predicates :numeric-fluents)"
              " (:predicates (q) (z)) (:functions (f))"
              " (:derived (q) (or (z) (<= (f) 5)))"
              " (:action set :parameters () :effect (assign (f) 3)))")
    d, p = _pair(tmp_path, domain, "(define (problem u) (:domain u) (:init) (:goal (q)))")
    dp = DomainProblem(d, p)
    assert ("q",) not in State.from_problem(dp).atoms
    assert not validate_plan(dp, []).valid
    for planner in ["bfs", "astar", "gbfs", "ucs"]:
        assert [n for n, _ in get(planner).solve(dp).action_names()] == ["set"]
    p2 = tmp_path / "p2.pddl"
    p2.write_text("(define (problem u) (:domain u) (:init (z)) (:goal (q)))")
    # (z) settles the or: the undefined comparison is not needed
    assert ("q",) in State.from_problem(DomainProblem(d, str(p2))).atoms


@pytest.mark.parametrize("rules, goal", [
    # review on #205: an undefined derived atom stays undefined under not
    ("(:derived (q) (<= (f) 5))", "(not (q))"),
    ("(:derived (q) (<= (f) 5)) (:derived (r) (not (q)))", "(r)"),
    # or in written order: the undefined comparison comes before (p)
    ("(:derived (q) (or (<= (f) 5) (p)))", "(q)"),
])
def test_undefined_derived_atoms_propagate(tmp_path, rules, goal):
    domain = ("(define (domain u) (:requirements :adl :derived-predicates :numeric-fluents)"
              " (:predicates (p) (q) (r)) (:functions (f)) " + rules +
              " (:action set :parameters () :effect (assign (f) 10))"
              " (:action set3 :parameters () :effect (assign (f) 3)))")
    d, p = _pair(tmp_path, domain, "(define (problem u) (:domain u) (:init (p)) (:goal %s))" % goal)
    dp = DomainProblem(d, p)
    failure = validate_plan(dp, []).failure
    assert failure.kind == "goal" and "no value for" in failure.message
    plan = get("bfs").solve(dp)
    assert len(plan) == 1
    assert validate_plan(dp, parse_plan("(%s)\n" % plan.action_names()[0][0])).valid


def test_precondition_reading_an_undefined_derived_atom(tmp_path):
    domain = ("(define (domain u) (:requirements :adl :derived-predicates :numeric-fluents)"
              " (:predicates (q) (done)) (:functions (f)) (:derived (q) (<= (f) 5))"
              " (:action use :parameters () :precondition (not (q)) :effect (done))"
              " (:action set :parameters () :effect (assign (f) 10)))")
    d, p = _pair(tmp_path, domain, "(define (problem u) (:domain u) (:init) (:goal (done)))")
    dp = DomainProblem(d, p)
    failure = validate_plan(dp, parse_plan("(use)\n")).failure
    assert failure.kind == "undefined-fluent" and failure.unmet == ("(q)",)
    assert [n for n, _ in get("bfs").solve(dp).action_names()] == ["set", "use"]


@pytest.mark.parametrize("rules, effect, goal", [
    # the reader comes before the rule it reads (review on #205)
    ("(:derived (r) (q)) (:derived (q) (<= (f) 5))", "(done)", "(and (done) (not (r)))"),
    # a conditional-effect guard reads an undefined derived atom
    ("(:derived (r) (q)) (:derived (q) (<= (f) 5))", "(when (not (q)) (done))", "(done)"),
    # a head already true through a later disjunct or a later rule
    ("(:derived (q) (<= (f) 5)) (:derived (r) (or (q) (p)))", "(done)", "(and (done) (r))"),
    ("(:derived (r) (or (q) (p))) (:derived (q) (<= (f) 5))", "(done)", "(and (done) (r))"),
    ("(:derived (q) (<= (f) 5)) (:derived (q) (p)) (:derived (r) (q))", "(done)", "(and (done) (r))"),
])
def test_undefined_reads_need_the_fluent_set(tmp_path, rules, effect, goal):
    domain = ("(define (domain u) (:requirements :adl :derived-predicates :numeric-fluents)"
              " (:predicates (p) (q) (r) (done)) (:functions (f)) %s"
              " (:action use :parameters () :precondition (and) :effect %s)"
              " (:action set :parameters () :effect (assign (f) 10)))" % (rules, effect))
    d, p = _pair(tmp_path, domain,
                 "(define (problem u) (:domain u) (:init (p)) (:goal %s))" % goal)
    dp = DomainProblem(d, p)
    assert ("#undefined", "r") in State.from_problem(dp).atoms
    assert not validate_plan(dp, parse_plan("(use)\n")).valid
    for name in ("bfs", "astar", "gbfs", "ucs"):
        plan = get(name).solve(dp)
        text = "".join("(%s)\n" % n for n, _ in plan.action_names())
        assert len(plan) == 2 and validate_plan(dp, parse_plan(text)).valid


@pytest.mark.parametrize("rules", [
    "(:derived (q) (<= (f) 5)) (:derived (r) (or (p) (q)))",
    "(:derived (q) (<= (f) 5)) (:derived (r) (p)) (:derived (r) (q))",
])
def test_a_true_body_before_an_undefined_one_settles_it(tmp_path, rules):
    """Review on #205, the VAL controls: the empty plan is valid."""
    domain = ("(define (domain u) (:requirements :adl :derived-predicates :numeric-fluents)"
              " (:predicates (p) (q) (r)) (:functions (f)) %s)" % rules)
    d, p = _pair(tmp_path, domain, "(define (problem u) (:domain u) (:init (p)) (:goal (r)))")
    dp = DomainProblem(d, p)
    assert validate_plan(dp, []).valid and len(get("bfs").solve(dp)) == 0


@pytest.mark.parametrize("rules, refused", [
    # review on #205: VAL's answer depends on where the recursion starts
    ("(:derived (q) (or (r) (p))) (:derived (r) (or (q) (<= (f) 5)))", "q, r"),
    ("(:derived (s) (<= (f) 5)) (:derived (q) (or (q) (s)))", "q"),
    ("(:derived (q) (or (r) (p))) (:derived (r) (q)) (:derived (s) (<= (f) 5))", None),
])
def test_recursion_through_numeric_reads_is_refused(tmp_path, rules, refused):
    domain = ("(define (domain u) (:requirements :adl :derived-predicates :numeric-fluents)"
              " (:predicates (p) (q) (r) (s)) (:functions (f)) %s"
              " (:action set :parameters () :effect (assign (f) 10)))" % rules)
    d, p = _pair(tmp_path, domain, "(define (problem u) (:domain u) (:init (p)) (:goal (q)))")
    dp = DomainProblem(d, p)
    if refused is None:
        assert len(get("bfs").solve(dp)) == 0
        return
    for check in (lambda: get("bfs").solve(dp), lambda: validate_plan(dp, [])):
        with pytest.raises(PlannerError, match="compare numeric fluents are not supported: %s" % refused):
            check()


def test_either_typed_rule_parameters(tmp_path):
    domain = ("(define (domain e) (:requirements :typing :derived-predicates)"
              " (:types a b) (:predicates (p ?x) (q ?x))"
              " (:derived (q ?x - (either a b)) (p ?x))"
              " (:action noop :parameters () :effect (and)))")
    d, p = _pair(tmp_path, domain, "(define (problem e) (:domain e) (:objects i - a j - b)"
                 " (:init (p i) (p j)) (:goal (and (q i) (q j))))")
    assert get("bfs").solve(DomainProblem(d, p)) is not None


def test_undefined_markers_are_not_serialized(tmp_path):
    from pddlpy.serialize import state_dict
    domain = ("(define (domain u) (:requirements :strips :derived-predicates :numeric-fluents)"
              " (:predicates (p) (q)) (:functions (f)) (:derived (q) (<= (f) 5))"
              " (:action noop :parameters () :effect (and)))")
    d, p = _pair(tmp_path, domain, "(define (problem u) (:domain u) (:init (p)) (:goal (p)))")
    state = State.from_problem(DomainProblem(d, p))
    assert ("#undefined", "q") in state.atoms
    assert state_dict(state)["atoms"] == [["p"]]
