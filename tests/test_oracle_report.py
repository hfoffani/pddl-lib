"""The oracle workflow's report (tests/oracle_report.py, #153)."""
import json
import sys

import oracle_report

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
<testcase classname="tests.test_oracle" name="test_accept_reject_agrees_with_fd[a/p01.pddl]"/>
<testcase classname="tests.test_oracle" name="test_accept_reject_agrees_with_fd[b/p01.pddl]">
  <failure message="AssertionError: FD translator exit 0&#10;assert False == True">trace</failure>
</testcase>
<testcase classname="tests.test_oracle" name="test_pddlpy_plan_passes_val[a/p01.pddl]">
  <skipped type="pytest.skip" message="VAL not found"/>
</testcase>
<testcase classname="tests.test_oracle" name="test_pddlpy_plan_passes_val[c/p01.pddl]">
  <skipped type="pytest.xfail" message="(:derived ...) does not parse (#141)"/>
</testcase>
<testcase classname="tests.test_oracle" name="test_solvability_agrees_with_fd[d/p01.pddl]">
  <error message="KeyError: go">trace</error>
</testcase>
</testsuite></testsuites>
"""


def test_report(tmp_path, monkeypatch, capsys):
    junit = tmp_path / "oracle.xml"
    junit.write_text(JUNIT)
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"potassco": {"crash": 2, "valid": 5}, "classical": {"valid": 1}}))
    monkeypatch.setattr(sys, "argv", ["oracle_report", "--title", "T", str(junit), str(summary)])
    oracle_report.main()
    out = capsys.readouterr().out
    assert out.startswith("## T\n")
    assert "**2 failures: 2 new, 0 with a known cause.**" in out
    assert "| `test_accept_reject_agrees_with_fd` | 1 | 1 | 1 | 0 | 0 |" in out
    assert "| `test_pddlpy_plan_passes_val` | 0 | 0 | 0 | 1 | 1 |" in out
    assert "- **NEW** `b/p01.pddl`: AssertionError: FD translator exit 0" in out
    assert "- **NEW** `d/p01.pddl`: KeyError: go" in out
    assert "| classical | 0 | 1 |" in out and "| potassco | 2 | 5 |" in out


def test_known_causes_mark_failures(tmp_path):
    """Failures with a known cause are tagged with it and listed after the
    new ones; the cause depends on both the check and the pair."""
    junit = tmp_path / "o.xml"
    junit.write_text("""<testsuite>
<testcase name="test_solvability_agrees_with_fd[potassco/ipc-2000/domains/blocks-strips-typed/instances/instance-1.pddl]"><failure message="assert False"/></testcase>
<testcase name="test_solvability_agrees_with_fd[classical/classical/termes-opt18/p01.pddl]"><failure message="assert False"/></testcase>
<testcase name="test_accept_reject_agrees_with_fd[potassco/ipc-2000/domains/blocks-strips-typed/instances/instance-1.pddl]"><failure message="exit 0"/></testcase>
</testsuite>""")
    text = oracle_report.report([str(junit)], "T")
    assert "**3 failures: 2 new, 1 with a known cause.**" in text
    lines = text.splitlines()
    termes = next(i for i, ln in enumerate(lines) if "termes" in ln)
    blocks = next(i for i, ln in enumerate(lines) if "known: #157" in ln)
    assert lines[termes].startswith("- **NEW**") and termes < blocks
    # #157 covers the plan and solvability checks, not acceptance
    assert "- **NEW** `potassco/ipc-2000/domains/blocks-strips-typed" in text
    assert oracle_report.known_cause("test_accept_reject_agrees_with_fd",
                                     "classical/classical/tyreworld/pfile1.pddl").startswith("FD rejects")
    # (VALUE C0 N0) in :init vs (value ?c ?v) in the domain (oracle run on main)
    for pair in ("classical/classical/thoughtful-sat14-strips/bootstrap-typed-01.pddl",
                 "potassco/ipc-2014/domains/thoughtful-sequential-satisficing/instances/"
                 "instance-1.pddl"):
        for check in ("test_fd_plan_replays_in_pddlpy_and_val",
                      "test_solvability_agrees_with_fd"):
            assert oracle_report.known_cause(check, pair).startswith("#157")


def test_long_failure_lists_are_capped(tmp_path, monkeypatch):
    cases = "".join(
        '<testcase name="test_x[p%d]"><failure message="m"/></testcase>' % i
        for i in range(oracle_report.MAX_LISTED + 3)
    )
    junit = tmp_path / "o.xml"
    junit.write_text("<testsuite>%s<testcase name='bare'/></testsuite>" % cases)
    text = oracle_report.report([str(junit)], "T")
    assert "... and 3 more" in text
    assert "| `bare` | 1 | 0 | 0 | 0 | 0 |" in text
