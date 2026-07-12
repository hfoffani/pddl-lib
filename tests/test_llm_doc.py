"""docs/llm-interaction.md (#99) stays honest: its commands really produce
the documented outputs — the courier pair validates clean and ucs finds the
7-cost three-hop detour, beating the direct highway (10) and the decoy (11).
"""
import json
import os

from pddlpy.cli import main

PDDL = os.path.join(os.path.dirname(__file__), os.pardir, "examples", "pddl")
DOMAIN = os.path.join(PDDL, "courier-domain.pddl")
PROBLEM = os.path.join(PDDL, "courier-problem.pddl")


def _run(capsys, *argv):
    code = main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_courier_pair_validates_clean(capsys):
    code, out = _run(capsys, "validate", DOMAIN, PROBLEM)
    assert code == 0
    assert out == {"valid": True, "issues": []}


def test_ucs_beats_the_intuitive_answers(capsys):
    code, out = _run(capsys, "solve", DOMAIN, PROBLEM, "--planner", "ucs")
    assert code == 0
    assert out["solved"] is True
    assert out["cost"] == 7.0  # < 10 (direct highway) and < 11 (junction decoy)
    hops = [(s["args"]["?from"], s["args"]["?to"]) for s in out["steps"]]
    assert hops == [
        ("depot", "riverside"),
        ("riverside", "oldbridge"),
        ("oldbridge", "town"),
    ]
