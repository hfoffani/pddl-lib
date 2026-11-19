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
#: scenarios answered with a plan
PLANS = [sc.name for sc in scenarios.all_scenarios() if sc.kind in ("solve", "improve-plan")]


@pytest.fixture(scope="module")
def plans():
    return {n: scenarios.check(scenarios.load(n)).plan for n in PLANS}


@pytest.mark.parametrize("name", ALL)
def test_reference_matches_meta(name):
    c = scenarios.check(scenarios.load(name))
    assert c.ok, c
    assert c.seconds < 10


@pytest.mark.parametrize("name", PLANS)
def test_grade_reference_plan_optimal(name, plans):
    g = grader.grade(scenarios.load(name), "Plan:\n" + "\n".join(plans[name]))
    assert g.verdict == grader.OPTIMAL, g


@pytest.mark.parametrize("name", PLANS)
def test_grade_truncated_plan_goal_not_reached(name, plans):
    g = grader.grade(scenarios.load(name), "\n".join(plans[name][:-1]))
    assert g.verdict in (grader.GOAL, grader.UNPARSEABLE), g
    if len(plans[name]) > 1:
        assert g.verdict == grader.GOAL


@pytest.mark.parametrize("name", PLANS)
def test_grade_unknown_object_invalid(name, plans):
    first = plans[name][0].strip("()").split()
    bogus = "(%s %s)" % (first[0], " ".join(["nowhere"] * (len(first) - 1)))
    g = grader.grade(scenarios.load(name), "\n".join([bogus] + plans[name]))
    assert g.verdict == grader.INVALID, g


@pytest.mark.parametrize("name", PLANS)
def test_grade_prose_unparseable(name):
    g = grader.grade(scenarios.load(name), "I am not sure, it depends.")
    assert g.verdict == grader.UNPARSEABLE


def test_regex_keeps_unknown_steps_for_the_extractor():
    sc = scenarios.load("courier")
    plan = "(drive depot riverside) (teleport riverside oldbridge) (drive oldbridge town)"
    assert grader.grade(sc, plan).verdict == grader.UNPARSEABLE  # no extractor
    replies = ["(drive depot riverside)\n(teleport riverside oldbridge)\n"
               "(drive oldbridge town)"]
    assert grader.grade(sc, plan, lambda p: replies[0]).verdict == grader.INVALID
    assert grader.grade(sc, "(drive depot riverside) (teleport) (drive riverside oldbridge)"
                            " (drive oldbridge town)").verdict == grader.UNPARSEABLE
    # prose in parentheses before or after the plan is fine
    good = "(drive depot riverside) (drive riverside oldbridge) (drive oldbridge town)"
    assert grader.grade(sc, "(see below) " + good).verdict == grader.OPTIMAL
    assert grader.grade(sc, good + " (total 7)").verdict == grader.OPTIMAL


def test_grade_suboptimal():
    sc = scenarios.load("courier")
    g = grader.grade(sc, "Just take the highway: (drive depot town)")
    assert (g.verdict, g.cost) == (grader.SUBOPTIMAL, 10.0)
    greedy = "(workat day1 madrid) (workat day2 madrid) (workat day3 paris)"
    g = grader.grade(scenarios.load("maintenance"), greedy)
    assert (g.verdict, g.cost) == (grader.SUBOPTIMAL, 3.0)


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
    replies = ["", "(drive depot town)"]
    assert grader.grade(sc, prose, lambda p: replies.pop(0)).verdict == grader.SUBOPTIMAL


def test_improve_plan_shows_a_valid_suboptimal_plan():
    sc = scenarios.load("maintenance-improve")
    g = grader.grade(sc, sc.proposed_file.read_text())
    assert (g.verdict, g.cost) == (grader.SUBOPTIMAL, 3.0)


def test_grade_check_plan():
    sc = scenarios.load("courier-check")
    assert sc.kind == "check-plan" and sc.first_bad_step == 16

    def verdict(answer):
        return grader.grade(sc, answer).verdict
    assert verdict("The road runs the other way.\nVERDICT: invalid at step 16") == grader.CORRECT
    assert verdict("**VERDICT:** Invalid at step 16.") == grader.CORRECT
    assert verdict("VERDICT: invalid at step 3\n...\nVERDICT: invalid at step 16") == grader.CORRECT
    assert verdict("VERDICT: invalid at step 17") == grader.WRONG
    assert verdict("VERDICT: valid") == grader.WRONG
    assert verdict("It fails at step 16.") == grader.UNPARSEABLE


def test_grade_unsolvable():
    sc = scenarios.load("courier-unsolvable")
    assert sc.optimal_cost is None
    assert grader.grade(sc, "This is impossible: nothing reaches the castle.").verdict \
        == grader.CORRECT
    # a plan instead gets that plan's verdict: here the tools never arrive
    reference = scenarios.check(scenarios.load("courier-parcels")).plan
    g = grader.grade(sc, "\n".join(reference))
    assert g.verdict == grader.INVALID, g
    assert grader.grade(sc, "Hmm.").verdict == grader.UNPARSEABLE
    assert grader.grade(sc, "The task is not impossible.").verdict == grader.UNPARSEABLE
    assert grader.grade(sc, "It isn't really unsolvable.").verdict == grader.UNPARSEABLE
    for hedged in ("The task might be impossible.", "It is probably impossible.",
                   "This seems impossible."):
        assert grader.grade(sc, hedged).verdict == grader.UNPARSEABLE, hedged
    # the extractor decides when there is one
    seen = []

    def fake(reply):
        def call(prompt):
            seen.append(prompt)
            return reply
        return call
    assert grader.grade(sc, "No route delivers the tools.", fake("YES")).verdict \
        == grader.CORRECT
    assert "cannot be done" in seen[0] and "every constraint" in seen[0]
    assert grader.grade(sc, "It is impossible to do better than 30.",
                        fake("NO")).verdict != grader.CORRECT


def test_codex_command_per_arm(tmp_path):
    import codex_driver as cx

    def cmd(arm):
        return cx.command(arm, "gpt-x", tmp_path, "uv run pddlpy-mcp")
    bare, py, pd = cmd("bare"), cmd("python"), cmd("pddlpy")
    off = {arm: {c[i + 1] for i in range(len(c) - 1) if c[i] == "--disable"}
           for arm, c in (("bare", bare), ("python", py), ("pddlpy", pd))}
    assert {"code_mode_host", "shell_tool", "skill_search"} <= off["bare"]
    assert "shell_tool" not in off["python"] and "code_mode_host" not in off["python"]
    assert "shell_tool" in off["pddlpy"] and "code_mode_host" not in off["pddlpy"]
    assert 'mcp_servers.pddlpy.command="uv"' in pd and "mcp_servers.pddlpy.command" not in \
        " ".join(py)
    assert bare[bare.index("-s") + 1] == "read-only" and py[py.index("-m") + 1] == "gpt-x"


def test_codex_events_to_messages():
    import codex_driver as cx
    events = [
        {"type": "item.completed", "item": {"type": "error", "message": "warn"}},
        {"type": "item.completed", "item": {"type": "reasoning", "text": "think"}},
        {"type": "item.completed", "item": {
            "type": "mcp_tool_call", "tool": "solve", "arguments": {"planner": "ucs"},
            "result": {"structured_content": {"result": {"status": "solved"}}}}},
        {"type": "item.completed", "item": {
            "type": "command_execution", "command": "python x.py",
            "aggregated_output": "7\n", "exit_code": 0}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Answer"}},
        {"type": "item.completed", "item": {"type": "reasoning", "text": "after"}},
        {"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
    ]
    msgs, tokens, errors = cx.to_messages(events)
    assert tokens == 15 and errors == ["warn"]
    calls = [m["tool_calls"][0]["function"]["name"] for m in msgs if m.get("tool_calls")]
    assert calls == ["solve", "shell"]
    assert json.loads(msgs[2]["content"]) == {"status": "solved"}
    assert playground.final_answer(msgs) == "Answer"


def test_transcript_answer():
    t = "# x\n\n## User\n\nq\n\n## Assistant\n\nthinking\n\n### `solve`\n\n{}\n" \
        "\n## Assistant\n\n## Answer\n\nImpossible.\n"
    assert playground.transcript_answer(t) == "## Answer\n\nImpossible."
    assert playground.transcript_answer(t.rsplit("\n## Assistant", 1)[0]) == ""
    assert playground.transcript_answer("# x\n") == ""


@pytest.mark.parametrize("stored", [True, False])
def test_regrade(tmp_path, stored):
    pytest.importorskip("httpx")
    if not stored:
        pytest.importorskip("mcp")
    playground.main(["run", "courier-unsolvable", "--arm", "bare", "--dry-run",
                     "--out", str(tmp_path)])
    path = tmp_path / "results.jsonl"
    rec = json.loads(path.read_text())
    assert rec["answer"].startswith("It is impossible")
    rec["verdict"] = "wrong"
    if not stored:
        rec["answer"] = ""
    path.write_text(json.dumps(rec) + "\n")
    assert playground.main(["regrade", str(tmp_path), "--grader-model", ""]) == 0
    assert json.loads(path.read_text())["verdict"] == grader.CORRECT
    assert "(regraded)" in (tmp_path / "results.md").read_text()
    text = (tmp_path / rec["transcript"]).read_text()
    assert "**verdict:** `correct`" in text and "## User" in text
    assert text.count("**graded plan**") == 1


def test_regrade_retries_grading_errors(tmp_path):
    pytest.importorskip("httpx")
    playground.main(["run", "courier", "--arm", "bare", "--dry-run", "--out", str(tmp_path)])
    path = tmp_path / "results.jsonl"
    rec = json.loads(path.read_text())
    rec.update(verdict="error", detail="grading failed: boom")
    path.write_text(json.dumps(rec) + "\n")
    playground.main(["regrade", str(tmp_path), "--grader-model", ""])
    assert json.loads(path.read_text())["verdict"] == grader.OPTIMAL


def test_codex_nonzero_exit_is_an_error(tmp_path, monkeypatch):
    import codex_driver as cx

    class Proc:
        returncode = 1

        async def communicate(self, data=None):
            return b"", b"boom: not logged in"

    async def fake_exec(*a, **k):
        return Proc()
    monkeypatch.setattr(cx.asyncio, "create_subprocess_exec", fake_exec)
    monkeypatch.setattr(cx, "codex_home", lambda w: tmp_path)
    run = playground.Run("courier", "bare", "codex:x", 1)
    with pytest.raises(RuntimeError, match="not logged in"):
        import asyncio
        asyncio.run(cx.converse(run, scenarios.load("courier"), "x", 5))


def test_server_cmd_keeps_spaces():
    import shlex
    cmd = "uv run --project %s pddlpy-mcp" % shlex.quote("/a b/c")
    assert shlex.split(cmd)[3] == "/a b/c"


needs_sandbox = pytest.mark.skipif(not sandbox.shutil.which("sandbox-exec"),
                                   reason="run_python needs sandbox-exec (macOS)")


@needs_sandbox
def test_sandbox_runs_code(tmp_path):
    out = json.loads(sandbox.run_python("print(6*7)", tmp_path))
    assert (out["exit_code"], out["stdout"]) == (0, "42\n")


@needs_sandbox
def test_sandbox_host_write_ignores_planted_symlink(tmp_path):
    work, outside = tmp_path / "work", tmp_path / "victim.txt"
    work.mkdir()
    outside.write_text("keep")
    (work / "run_1.py").symlink_to(outside)
    out = json.loads(sandbox.run_python("print('ok')", work, n=1))
    assert out["stdout"] == "ok\n" and outside.read_text() == "keep"


@needs_sandbox
def test_sandbox_bounds_output(tmp_path):
    out = json.loads(sandbox.run_python("print('x' * 50000)", tmp_path))
    assert len(out["stdout"]) < sandbox.MAX_OUTPUT + 100
    assert "truncated 40001 bytes" in out["stdout"]


@needs_sandbox
def test_sandbox_returns_despite_children_holding_the_pipes(tmp_path):
    import time
    code = ("import subprocess, os\n"
            "subprocess.Popen(['/bin/sleep', '30'])\n"
            "subprocess.Popen(['/bin/sleep', '30'], start_new_session=True)\n"
            "print('parent done')\n")
    t0 = time.monotonic()
    out = json.loads(sandbox.run_python(code, tmp_path, timeout=10))
    assert time.monotonic() - t0 < 8 and out["stdout"].startswith("parent done")


@needs_sandbox
def test_sandbox_timeout(tmp_path):
    out = json.loads(sandbox.run_python("while True: pass", tmp_path, timeout=1))
    assert out["exit_code"] is None and out["timed_out_after_seconds"] == 1


@needs_sandbox
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


@pytest.mark.parametrize("name", ["courier", "courier-check", "courier-unsolvable"])
@pytest.mark.parametrize("arm", playground.ARMS)
def test_dry_run(arm, name, tmp_path):
    if arm == "pddlpy":
        pytest.importorskip("mcp")
    pytest.importorskip("httpx")
    rc = playground.main(["run", name, "--arm", arm, "--dry-run", "--out", str(tmp_path)])
    assert rc == 0
    rec = json.loads((tmp_path / "results.jsonl").read_text().splitlines()[0])
    assert rec["verdict"] in grader.PASS, rec
    assert "| %s | %s | 1/1 |" % (name, arm) in (tmp_path / "results.md").read_text()
