"""Offline checks for the playground (no API key). Not collected by `make`:

    uv run --with mcp,httpx pytest e2e/llm
"""
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))

import grader  # noqa: E402
import playground  # noqa: E402
import sandbox  # noqa: E402
import scenarios  # noqa: E402

ALL = [sc.name for sc in scenarios.all_scenarios()]


@pytest.fixture(scope="module")
def plans():
    return {n: scenarios.check(scenarios.load(n)).plan for n in ALL}


@pytest.mark.parametrize("name", ALL)
def test_reference_solves_at_optimum(name, plans):
    sc = scenarios.load(name)
    c = scenarios.check(sc)
    assert c.cost == sc.optimal_cost
    assert c.seconds < 10


@pytest.mark.parametrize("name", ALL)
def test_grade_reference_plan_optimal(name, plans):
    g = grader.grade(scenarios.load(name), "Plan:\n" + "\n".join(plans[name]))
    assert g.verdict == grader.OPTIMAL, g


@pytest.mark.parametrize("name", ALL)
def test_grade_truncated_plan_goal_not_reached(name, plans):
    g = grader.grade(scenarios.load(name), "\n".join(plans[name][:-1]))
    assert g.verdict in (grader.GOAL, grader.UNPARSEABLE), g
    if len(plans[name]) > 1:
        assert g.verdict == grader.GOAL


@pytest.mark.parametrize("name", ALL)
def test_grade_out_of_order_plan_invalid(name, plans):
    g = grader.grade(scenarios.load(name), "\n".join(reversed(plans[name])))
    assert g.verdict == grader.INVALID, g


@pytest.mark.parametrize("name", ALL)
def test_grade_prose_unparseable(name):
    g = grader.grade(scenarios.load(name), "I am not sure, it depends.")
    assert g.verdict == grader.UNPARSEABLE


def test_grade_suboptimal():
    sc = scenarios.load("courier")
    g = grader.grade(sc, "Just take the highway: (drive depot town)")
    assert (g.verdict, g.cost) == (grader.SUBOPTIMAL, 10.0)


def test_grade_extractor_path():
    sc = scenarios.load("courier")
    prose = "Go depot, riverside, old bridge, then town. Total 7."
    seen = []

    def fake(prompt):
        seen.append(prompt)
        return "```\n(drive depot riverside)\n(drive riverside oldbridge)\n" \
               "(drive oldbridge town)\n```"
    g = grader.grade(sc, prose, fake)
    assert (g.verdict, g.source) == (grader.OPTIMAL, "extractor")
    assert "(drive ?from - place ?to - place)" in seen[0] and prose in seen[0]
    assert grader.grade(sc, prose, lambda p: "NONE").verdict == grader.UNPARSEABLE


def test_sandbox_runs_code(tmp_path):
    out = json.loads(sandbox.run_python("print(6*7)", tmp_path))
    assert (out["exit_code"], out["stdout"]) == (0, "42\n")


def test_sandbox_timeout(tmp_path):
    out = json.loads(sandbox.run_python("while True: pass", tmp_path, timeout=1))
    assert out["exit_code"] is None and out["timed_out_after_seconds"] == 1


def test_sandbox_has_no_pddlpy(tmp_path):
    out = json.loads(sandbox.run_python("import pddlpy", tmp_path))
    assert "ModuleNotFoundError" in out["stderr"]


@pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS only")
def test_sandbox_blocks_network_and_outside_writes(tmp_path):
    code = ("import urllib.request\n"
            "try:\n urllib.request.urlopen('https://example.com', timeout=5); print('net')\n"
            "except Exception: print('no-net')\n"
            "try:\n open('%s', 'w'); print('wrote')\n"
            "except Exception: print('no-write')\n"
            "open('inside.txt', 'w').write('ok')\n" % (HERE / "escape.txt"))
    out = json.loads(sandbox.run_python(code, tmp_path))
    assert out["stdout"].split() == ["no-net", "no-write"]
    assert (tmp_path / "inside.txt").read_text() == "ok"


@pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS only")
def test_sandbox_blocks_reads_outside(tmp_path):
    code = "open(%r).read()" % str(pathlib.Path(__file__).resolve())
    out = json.loads(sandbox.run_python(code, tmp_path))
    assert "PermissionError" in out["stderr"], out


def test_sandbox_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: None)
    out = json.loads(sandbox.run_python("print(1)", tmp_path))
    assert "no sandbox" in out["error"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("arm", playground.ARMS)
def test_dry_run(arm, tmp_path):
    if arm == "pddlpy":
        pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    rc = playground.main(["run", "courier", "--arm", arm, "--dry-run", "--out", str(tmp_path)])
    assert rc == 0
    rec = json.loads((tmp_path / "results.jsonl").read_text().splitlines()[0])
    assert rec["verdict"] == grader.OPTIMAL, rec
    assert "| courier | %s | 1/1 |" % arm in (tmp_path / "results.md").read_text()
