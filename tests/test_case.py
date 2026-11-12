"""#157: PDDL identifiers are case-insensitive. Names are lowercased at
parse time, as Fast Downward and VAL print them, so (CLEAR C) in :init
matches (clear ?x - block) and plans may use any case."""
from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import atom_tuple, get
from pddlpy.planning.validation import load_plan, validate_plan

DOMAIN = ("(define (domain T) (:requirements :strips :typing) (:types Block)"
          " (:predicates (Clear ?x - block) (On ?x ?y - BLOCK) (OBJ ?x))"
          " (:action Unstack :parameters (?X - Block ?Y - block)"
          "  :precondition (and (on ?x ?Y) (CLEAR ?x) (obj ?y))"
          "  :effect (and (Clear ?y) (not (ON ?X ?y)))))")
PROBLEM = ("(define (problem P) (:domain t) (:objects A B - block)"
           " (:init (ON a B) (clear A) (Obj b)) (:goal (CLEAR b)))")


def _pair(tmp_path):
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    d.write_text(DOMAIN)
    p.write_text(PROBLEM)
    return str(d), str(p)


def test_names_are_lowercased_and_match(tmp_path):
    d, p = _pair(tmp_path)
    dp = DomainProblem(d, p)
    assert {atom_tuple(a) for a in dp.initialstate()} == {
        ("on", "a", "b"), ("clear", "a"), ("obj", "b")}
    assert dp.worldobjects() == {"a": "block", "b": "block"}
    # static (obj ?y) prunes every grounding but ?y = b
    assert sorted(o.variable_list["?y"] for o in dp.ground_operator("unstack")) == ["b", "b"]
    assert diagnose(d, p) == {"valid": True, "issues": []}
    plan = get("bfs").solve(dp)
    assert plan is not None and len(plan) == 1


def test_plans_match_in_any_case(tmp_path):
    dp = DomainProblem(*_pair(tmp_path))
    for text in ("(UNSTACK A b)\n", '[{"action": "UnStack", "args": ["A", "B"]}]',
                 '[{"action": "unstack", "args": {"?X": "A", "?y": "b"}}]'):
        assert validate_plan(dp, load_plan(text)).valid, text


def test_grounding_entry_points_match_in_any_case(tmp_path):
    """Review on #190: callers may spell action names as the domain does."""
    dp = DomainProblem(*_pair(tmp_path))
    assert len(list(dp.ground_operator("Unstack"))) == 2
    assert dp.ground("UNSTACK", {"?x": "a", "?y": "b"}).operator_name == "unstack"
