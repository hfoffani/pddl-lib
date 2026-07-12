"""The pddlpy CLI (#85): parse / ground / solve emit JSON with sane exit codes."""
import json
import os

import pytest

from pddlpy.cli import main

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def _files(name):
    return (
        os.path.join(CORPUS, "%s-domain.pddl" % name),
        os.path.join(CORPUS, "%s-problem.pddl" % name),
    )


def _run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    out = json.loads(captured.out) if captured.out else None
    return code, out, captured.err


# --- parse ---------------------------------------------------------------

def test_parse_summary(capsys):
    code, out, err = _run(capsys, "parse", *_files("blocksworld"))
    assert code == 0 and err == ""
    assert "pick-up" in out["operators"]
    assert out["durative_operators"] == []
    assert ["handempty"] in out["initial_state"]
    assert ["on", "a", "b"] in out["goals"]
    assert out["metric"] is None
    assert out["initial_numeric"] == {}
    assert out["objects"]["a"] is None  # untyped domain


def test_parse_numeric_metric_and_types(capsys):
    code, out, err = _run(capsys, "parse", *_files("travel"))
    assert code == 0
    assert out["metric"] == {"optimization": "minimize", "expression": "(total-cost)"}
    assert out["initial_numeric"]["total-cost"] == 0.0
    assert out["types"] == {"place": None}
    assert ":action-costs" in out["requirements"]
    assert "at" in out["predicates"]


def test_parse_durative(capsys):
    code, out, _ = _run(capsys, "parse", *_files("durative-action"))
    assert code == 0
    assert out["durative_operators"] == ["go"]


def test_parse_missing_file(capsys):
    code, out, err = _run(capsys, "parse", "nosuch-domain.pddl", "nosuch-problem.pddl")
    assert code == 2 and out is None
    assert "pddlpy: error:" in err


# --- ground --------------------------------------------------------------

def test_ground_operator(capsys):
    code, out, _ = _run(capsys, "ground", *_files("blocksworld"), "pick-up")
    assert code == 0
    assert out["operator"] == "pick-up"
    groundings = out["groundings"]
    g = next(g for g in groundings if g["parameters"] == {"?x": "a"})
    assert g["name"] == "pick-up"
    assert g["precondition_connective"] == "and"
    assert list(g["parameters"]) == ["?x"]
    assert ["handempty"] in g["precondition_pos"]
    assert ["holding", g["parameters"]["?x"]] in g["effect_pos"]


def test_ground_numeric_reprs(capsys):
    code, out, _ = _run(capsys, "ground", *_files("numeric-transport"), "drive")
    assert code == 0
    g = out["groundings"][0]
    assert any(">=" in c for c in g["precondition_num"])
    assert any("decrease" in e for e in g["effect_num"])


def test_ground_unknown_operator(capsys):
    code, out, err = _run(capsys, "ground", *_files("blocksworld"), "fly")
    assert code == 2 and out is None
    assert "unknown operator 'fly'" in err and "pick-up" in err


# --- solve ---------------------------------------------------------------

def test_solve_default_planner(capsys):
    code, out, _ = _run(capsys, "solve", *_files("blocksworld"))
    assert code == 0
    assert out["planner"] == "astar" and out["solved"] is True
    assert out["length"] == len(out["steps"]) > 0
    step = out["steps"][0]
    assert set(step) == {"action", "args"}


def test_solve_cost_aware(capsys):
    code, out, _ = _run(capsys, "solve", *_files("travel"), "--planner", "ucs")
    assert code == 0
    assert out["solved"] is True and out["cost"] > 0


def test_solve_no_plan(capsys, tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain toy) (:predicates (p) (q))"
        " (:action a :parameters () :precondition (q) :effect (p)))"
    )
    problem.write_text(
        "(define (problem t1) (:domain toy) (:init) (:goal (p)))"
    )
    code, out, _ = _run(capsys, "solve", str(domain), str(problem), "--planner", "bfs")
    assert code == 1
    assert out == {
        "planner": "bfs", "solved": False, "cost": None, "length": None, "steps": None,
    }


def test_solve_unsupported_requirements(capsys, tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain toy) (:requirements :adl) (:predicates (p))"
        " (:action a :parameters () :precondition (p) :effect (p)))"
    )
    problem.write_text(
        "(define (problem t1) (:domain toy) (:init (p)) (:goal (p)))"
    )
    code, out, err = _run(capsys, "solve", str(domain), str(problem))
    assert code == 2 and out is None
    assert "pddlpy: error:" in err


def test_solve_unknown_planner_rejected_by_argparse(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["solve", *_files("blocksworld"), "--planner", "nosuch"])
    assert exc.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_missing_subcommand_rejected(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
