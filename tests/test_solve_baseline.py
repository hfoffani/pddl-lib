"""The solve baseline runner (tests/solve_baseline.py, M2) on a fake corpora
tree and a stub Fast Downward: rows, resume, limits, refusal causes and the
summary."""
import csv
import os
import sys
import textwrap

import pytest
import solve_baseline as sb
from test_corpora_run import fake_corpora

DURATIVE = """(define (domain d)
 (:requirements :strips :durative-actions :equality)
 (:predicates (p ?x) (q))
 (:durative-action a :parameters (?x ?y) :duration (= ?duration 2)
   :condition (over all (not (= ?x ?y))) :effect (at end (q))))"""

SIMPLE = """(define (domain d)
 (:requirements :strips :durative-actions)
 (:predicates (q))
 (:durative-action a :parameters () :duration (= ?duration 2)
   :condition (and) :effect (at end (q))))"""

PROBLEM = "(define (problem p) (:domain d) (:objects o1 o2) (:init) (:goal (q)))"


def run(monkeypatch, root, **env):
    monkeypatch.setenv("CORPORA_DIR", str(root))
    monkeypatch.setenv("BASELINE_JOBS", "1")
    for k in ("BASELINE_OUT", "DOMAIN", "CORPORA_PER_DOMAIN", "BASELINE_TIMEOUT",
              "BASELINE_RUNNERS", "BASELINE_MEMORY_GB"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return sb.main()


def rows(root, name="baseline-t10-nall"):
    with open(root / "results" / name / "baseline.csv", newline="") as f:
        return list(csv.DictReader(f))


def no_fd(monkeypatch, tmp_path):
    monkeypatch.delenv("FAST_DOWNWARD", raising=False)
    monkeypatch.setenv("ORACLES_DIR", str(tmp_path / "no-oracles"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")


def test_pddlpy_rows_summary_and_resume(tmp_path, monkeypatch, capsys):
    fake_corpora(tmp_path)
    no_fd(monkeypatch, tmp_path)
    assert run(monkeypatch, tmp_path, DOMAIN="ipc-2000",
               BASELINE_RUNNERS="bfs,astar,fd-opt") == 0
    got = {(r["runner"], r["status"]) for r in rows(tmp_path)}
    assert got == {("bfs", "solved"), ("astar", "solved"), ("fd-opt", "missing")}
    bfs = next(r for r in rows(tmp_path) if r["runner"] == "bfs")
    assert bfs["validated"] == "True" and bfs["phase"] == ""
    assert float(bfs["cost"]) == float(bfs["length"]) > 0
    assert int(bfs["expansions"]) > 0
    assert all(bfs[k] for k in ("parse_s", "ground_s", "search_s", "total_s"))
    assert bfs["variant"] == "potassco/ipc-2000/domains/blocks"
    assert "Fast Downward not found" in capsys.readouterr().out
    summary = (tmp_path / "results" / "baseline-t10-nall" / "summary.md").read_text()
    assert "| bfs | 1 |" in summary
    assert "| potassco/ipc-2000/domains/blocks | 1 | 1 | 1 | 0 |" in summary
    # A second run finds every row done.
    assert run(monkeypatch, tmp_path, DOMAIN="ipc-2000",
               BASELINE_RUNNERS="bfs,astar,fd-opt") == 0
    assert "3 runs left" not in capsys.readouterr().out
    assert len(rows(tmp_path)) == 3


def test_unknown_runner_and_empty_corpora(tmp_path, monkeypatch, capsys):
    assert run(monkeypatch, tmp_path, BASELINE_RUNNERS="bfs,lama") == 2
    assert "unknown runners ['lama']" in capsys.readouterr().out
    assert run(monkeypatch, tmp_path / "missing") == 0
    assert "no domain/problem pairs" in capsys.readouterr().out


def durative_corpora(root, domain):
    v = root / "potassco" / "ipc-2002" / "domains" / "t"
    (v / "instances").mkdir(parents=True)
    (v / "domain.pddl").write_text(domain)
    (v / "instances" / "instance-1.pddl").write_text(PROBLEM)


def test_durative_pairs(tmp_path, monkeypatch):
    durative_corpora(tmp_path, DURATIVE)
    assert run(monkeypatch, tmp_path, BASELINE_RUNNERS="bfs,temporal,validate") == 0
    by = {r["runner"]: r for r in rows(tmp_path)}
    assert by["bfs"]["status"] == "refused"
    assert sb.cause(by["bfs"]["message"]) == "planner does not support [':durative-actions']"
    assert by["validate"]["status"] == "refused"
    assert by["validate"]["message"] == "durative actions with equality parts"
    assert by["temporal"]["status"] == "refused"


def test_durative_pairs_accepted(tmp_path, monkeypatch):
    durative_corpora(tmp_path, SIMPLE)
    assert run(monkeypatch, tmp_path, BASELINE_RUNNERS="temporal,validate") == 0
    by = {r["runner"]: r for r in rows(tmp_path)}
    assert by["validate"]["status"] == "accepted"
    assert by["temporal"]["status"] == "solved"
    assert float(by["temporal"]["cost"]) == 2


def test_durative_only_runners_skip_classical_pairs(tmp_path, monkeypatch):
    fake_corpora(tmp_path)
    assert run(monkeypatch, tmp_path, DOMAIN="ipc-2000",
               BASELINE_RUNNERS="temporal,validate") == 0
    assert rows(tmp_path) == []


STUB_FD = """
import os, sys
args = sys.argv[1:]
plan = args[args.index("--plan-file") + 1]
if "--alias" in args:
    sys.exit(34)
with open(plan, "w") as f:
    f.write("(pick-up a)\\n; cost = 7 (unit cost)\\n")
print("[t=0.1s, 100 KB] Expanded 12 state(s).")
"""


def test_fd_rows_from_a_stub(tmp_path, monkeypatch):
    fake_corpora(tmp_path)
    stub = tmp_path / "fd.py"
    stub.write_text(STUB_FD)
    monkeypatch.setenv("FAST_DOWNWARD", str(stub))
    assert run(monkeypatch, tmp_path, DOMAIN="ipc-2000",
               BASELINE_RUNNERS="fd-opt,fd-sat") == 0
    by = {r["runner"]: r for r in rows(tmp_path)}
    assert (by["fd-opt"]["status"], by["fd-opt"]["cost"], by["fd-opt"]["expansions"],
            by["fd-opt"]["message"]) == ("solved", "7", "12", "")
    assert (by["fd-sat"]["status"], by["fd-sat"]["message"]) == ("refused", "exit 34")


def test_run_limited_kills_the_group(tmp_path):
    sleep = [sys.executable, "-c", "import time; time.sleep(30)"]
    code, _, reason, seconds = sb.run_limited(sleep, 0.6, 2**40)
    assert (code, reason) == (None, "timeout") and seconds < 10
    code, _, reason, _ = sb.run_limited(sleep, 30, 1)
    assert (code, reason) == (None, "memout")
    code, out, reason, _ = sb.run_limited([sys.executable, "-c", "print(1)"], 30, 2**40)
    assert (code, out, reason) == (0, "1\n", None)


def test_killed_child_keeps_its_phase(monkeypatch):
    monkeypatch.setattr(sb, "run_limited", lambda *a: (
        None, '{"phase": "parse"}\n{"parse_s": 1.5}\n{"phase": "ground"}\nnoise\n',
        "timeout", 16.0))
    row = sb.pddlpy_row("bfs", "d", "p", 10, 1)
    assert row == {"phase": "ground", "parse_s": 1.5, "status": "timeout", "total_s": 16.0}
    monkeypatch.setattr(sb, "run_limited", lambda *a: (1, "", None, 0.1))
    assert sb.pddlpy_row("bfs", "d", "p", 10, 1)["message"] == "child exited 1"


def test_fd_status_map(tmp_path, monkeypatch):
    for code, status in ((0, "solved"), (11, "unsolvable"), (12, "limit"),
                         (23, "timeout"), (22, "memout"), (31, "refused"), (99, "error")):
        monkeypatch.setattr(sb, "run_limited", lambda *a, c=code, **k: (c, "", None, 0.1))
        assert sb.fd_row("fd", "fd-opt", "d", "p", 10, 1)["status"] == status
    monkeypatch.setattr(sb, "run_limited", lambda *a, **k: (None, "", "memout", 0.1))
    assert sb.fd_row("fd", "fd-opt", "d", "p", 10, 1)["status"] == "memout"


@pytest.mark.parametrize("body, causes", [
    ("(:duration (= ?duration (fuel ?x)) :condition (and))", {"duration-expression"}),
    ("(:duration (and (>= ?duration (f)) (<= ?duration 3)))", {"duration-expression"}),
    ("(:duration (= ?duration 2) :condition (at start (>= (f) 1)))", {"numeric"}),
    ("(:duration (= ?duration 2) :effect (at end (increase (f) 1)))", {"numeric"}),
    ("(:duration (= ?duration 2) :effect (at end (when (p) (q))))", {"conditional"}),
    ("(:duration (= ?duration 2) :effect (forall (?y) (at end (q))))", {"quantified"}),
    ("(:duration (= ?duration 2) :effect (increase (f) (* #t 2)))", {"continuous", "numeric"}),
    ("(:duration (= ?duration 2) :condition (at start (= ?x ?y)))", {"equality"}),
    ("(:duration (= ?duration 2))", {"other"}),
])
def test_durative_causes(body, causes):
    text = textwrap.dedent("""
        (define (domain d)
         (:durative-action other :parameters () :effect (when (p) (q)))
         ; (:durative-action A (when commented out))
         (:durative-action A :parameters (?x ?y) %s))""") % body
    assert sb.durative_causes(text, ["A"]) == causes


def test_durative_causes_without_the_action():
    assert sb.durative_causes("(define (domain d))", ["a"]) == {"other"}
    assert sb._block("(a (b)", 0) == "(a (b)"


def test_cause_drops_names():
    assert sb.cause("durative action 'turn_to' has no simple numeric duration") == \
        "durative action 'X' has no simple numeric duration"
    assert sb.cause("temporal planner supports only ...; turn_to has numeric parts") == \
        "temporal planner supports only ...; X has numeric parts"
    assert sb.cause("BFSPlanner does not support [':fluents']") == \
        "planner does not support [':fluents']"


def test_summary_sections():
    def row(runner, status, **kw):
        base = dict(corpus="c", variant="v", domain="d", problem="p1", runner=runner,
                    status=status, phase="", cost="", length="", expansions="",
                    parse_s="", ground_s="", search_s="", total_s="1",
                    validated="", message="")
        base.update(kw)
        return base
    text = sb.summary([
        row("bfs", "timeout", phase="ground"),
        row("astar", "limit", parse_s="0.1", ground_s="0.2", search_s="2",
            expansions="1000"),
        row("ucs", "invalid", message="step 1 failed"),
        row("fd-opt", "solved", cost="3"),
        row("bfs", "solved", problem="p2"),
        row("fd-sat", "refused", message="exit 31"),
    ])
    assert "FD only 1, pddlpy only 1" in text
    assert "| bfs | timeout | ground | 1 |" in text
    assert "| astar | 1 | 0.1 | 0.2 | 2 | 500 |" in text
    assert "| fd-sat | exit 31 | 1 |" in text
    assert "| ucs | p1 | invalid | step 1 failed |" in text
    assert "| v | 2 | 1 |" in text


def test_summary_command(tmp_path, monkeypatch):
    fake_corpora(tmp_path)
    no_fd(monkeypatch, tmp_path)
    assert run(monkeypatch, tmp_path, DOMAIN="ipc-2000", BASELINE_RUNNERS="bfs") == 0
    summary = tmp_path / "results" / "baseline-t10-nall" / "summary.md"
    os.remove(summary)
    sb.write_summary(str(summary.with_name("baseline.csv")))
    assert summary.read_text().startswith("# Solve baseline")
