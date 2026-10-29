"""The pddlpy CLI (#85): parse / ground / solve emit JSON with sane exit codes."""
import io
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
    # one grounding per world object -- predicate names must not bind ?x
    assert len(groundings) == 3
    assert {g["parameters"]["?x"] for g in groundings} == {"a", "b", "c"}
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


def test_solve_temporal_schedule(capsys):
    # #119: TemporalPlan steps carry the schedule, plus a top-level makespan.
    code, out, _ = _run(
        capsys, "solve", *_files("temporal-weld"), "--planner", "temporal"
    )
    assert code == 0
    assert out["solved"] is True
    assert out["makespan"] == out["cost"] == 6.0
    step = out["steps"][0]
    assert set(step) == {"action", "args", "start", "duration", "end"}
    assert step["action"] == "steady-weld" and step["args"] == {"?p": "p1"}
    assert step["start"] == 0.0 and step["duration"] == 6.0 and step["end"] == 6.0


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
    # :durative-actions is beyond the blind planners' capabilities (ADL is now
    # supported, #10); the solve must still fail fast.
    domain.write_text(
        "(define (domain toy) (:requirements :durative-actions) (:predicates (p))"
        " (:action a :parameters () :precondition (p) :effect (p)))"
    )
    problem.write_text(
        "(define (problem t1) (:domain toy) (:init (p)) (:goal (p)))"
    )
    code, out, err = _run(capsys, "solve", str(domain), str(problem))
    assert code == 2 and out is None
    assert "pddlpy: error:" in err


# --- validate ------------------------------------------------------------

def test_validate_clean_pair(capsys):
    code, out, err = _run(capsys, "validate", *_files("blocksworld"))
    assert code == 0 and err == ""
    assert out == {"valid": True, "issues": []}


def test_validate_reports_issues_with_exit_1(capsys, tmp_path):
    domain = tmp_path / "d.pddl"
    problem = tmp_path / "p.pddl"
    domain.write_text(
        "(define (domain toy) (:predicates (p ?x))"
        " (:action a :parameters (?x) :precondition (p ?x) :effect (r ?x)))"
    )
    problem.write_text(
        "(define (problem t) (:domain toy) (:objects o1) (:init (p o1)) (:goal (p o1)))"
    )
    code, out, _ = _run(capsys, "validate", str(domain), str(problem))
    assert code == 1
    assert out["valid"] is False
    assert out["issues"][0]["check"] == "undeclared_predicate"


def test_validate_missing_file(capsys):
    code, out, err = _run(capsys, "validate", "nosuch-d.pddl", "nosuch-p.pddl")
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


# --- validate-plan / simulate (#166) ----------------------------------------

def _plan(tmp_path, text):
    path = tmp_path / "plan"
    path.write_text(text)
    return str(path)


def test_validate_plan_from_solve_output(capsys, monkeypatch):
    _, solved, _ = _run(capsys, "solve", *_files("gripper"))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(solved)))
    code, out, err = _run(capsys, "validate-plan", *_files("gripper"), "-")
    assert code == 0 and err == ""
    assert out == {"valid": True, "failure": None}


def test_validate_plan_reports_failure(capsys, tmp_path):
    plan = _plan(tmp_path, "(move rooma roomb)\n(move rooma roomb)\n")
    code, out, _ = _run(capsys, "validate-plan", *_files("gripper"), plan)
    assert code == 1 and out["valid"] is False
    f = out["failure"]
    assert (f["kind"], f["step"], f["action"]) == ("precondition", 2, "(move rooma roomb)")
    assert f["unmet"] == ["(at-robby rooma)"]
    assert ["at-robby", "roomb"] in f["state"]["atoms"]


def test_simulate_trace(capsys, tmp_path):
    plan = _plan(tmp_path, "0: (go a b) [5]\n")
    code, out, _ = _run(capsys, "simulate", *_files("durative-action"), plan)
    assert code == 0 and out["executed"] is True and out["failure"] is None
    assert [(p["time"], p["event"], p["step"]) for p in out["trace"]] == [
        (0.0, "start", 1), (5.0, "end", 1)]
    assert out["final_state"] == out["trace"][-1]["state"]


def test_simulate_failure_exit_1(capsys, tmp_path):
    plan = _plan(tmp_path, "0: (go b a) [5]\n")
    code, out, _ = _run(capsys, "simulate", *_files("durative-action"), plan)
    assert code == 1 and out["failure"]["kind"] == "precondition"


def test_numeric_state_rendering(capsys, tmp_path):
    _, solved, _ = _run(capsys, "solve", "--planner", "ucs", *_files("travel"))
    plan = _plan(tmp_path, json.dumps(solved))
    code, out, _ = _run(capsys, "simulate", *_files("travel"), plan)
    assert code == 0 and out["final_state"]["fluents"]["total-cost"] == 2.0


@pytest.mark.parametrize("plan", ["nosuch.plan", None])
def test_validate_plan_bad_input(capsys, tmp_path, plan):
    path = plan or _plan(tmp_path, "not a plan\n")
    code, out, err = _run(capsys, "validate-plan", *_files("blocksworld"), path)
    assert code == 2 and out is None and "pddlpy: error:" in err


@pytest.mark.parametrize("command", ["validate-plan", "simulate"])
def test_plan_not_utf8_is_bad_input(capsys, tmp_path, command):
    """Undecodable plan bytes are unreadable input (exit 2), not a verdict."""
    path = tmp_path / "plan"
    path.write_bytes(b"; caf\xe9\n(pick-up a)\n")  # Latin-1 comment
    code, out, err = _run(capsys, command, *_files("blocksworld"), str(path))
    assert code == 2 and out is None and "pddlpy: error:" in err


def test_non_finite_fluents_stay_strict_json(capsys, tmp_path):
    """IEEE division by zero: the output parses as strict JSON (no bare
    Infinity / NaN) and names the values."""
    domain = tmp_path / "d.pddl"
    domain.write_text("(define (domain d) (:requirements :fluents) (:predicates (p))"
                      " (:functions (f) (g) (z)) (:action a :parameters () :precondition (and)"
                      " :effect (and (p) (assign (f) (/ 1 0)) (assign (g) (/ (- 0 1) 0))"
                      " (assign (z) (/ 0 0)))))")
    problem = tmp_path / "p.pddl"
    problem.write_text("(define (problem p) (:domain d) (:init (= (f) 0) (= (g) 0) (= (z) 0))"
                       " (:goal (p)))")
    code = main(["simulate", str(domain), str(problem), _plan(tmp_path, "(a)\n")])
    text = capsys.readouterr().out

    def strict(token):
        raise ValueError("non-strict JSON literal %s" % token)

    out = json.loads(text, parse_constant=strict)
    assert code == 0
    assert out["final_state"]["fluents"] == {"f": "inf", "g": "-inf", "z": "nan"}


def test_validate_plan_refused(capsys, tmp_path):
    ipc = os.path.join(CORPUS, "ipc", "elevator-adl-full-typed")
    code, _, err = _run(capsys, "validate-plan", os.path.join(ipc, "domain.pddl"),
                        os.path.join(ipc, "p01.pddl"), _plan(tmp_path, ""))
    assert code == 2 and "#138" in err
