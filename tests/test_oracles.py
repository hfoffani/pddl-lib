"""The oracle wrappers (tests/oracles.py, #153) against fake binaries that
mimic the real tools' exit codes, plan files and verdict lines."""
import os
import stat
import sys

import oracles
from golden import IPC

GRIPPER = os.path.join(IPC, "gripper-round-1-strips")
DOMAIN = os.path.join(GRIPPER, "domain.pddl")
PROBLEM = os.path.join(GRIPPER, "p01.pddl")
PLAN = os.path.join(GRIPPER, "plans", "p01.plan")


def script(path, body):
    path.write_text("#!%s\nimport os, sys, time\n%s\n" % (sys.executable, body))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


FAKE_FD = """
args = sys.argv[1:]
if os.environ.get("FAKE_SLEEP"):
    time.sleep(5)
if "--plan-file" in args and os.environ.get("FAKE_PLAN"):
    with open(args[args.index("--plan-file") + 1], "w") as f:
        f.write(os.environ["FAKE_PLAN"])
sys.exit(int(os.environ.get("FAKE_CODE", "0")))
"""


def test_find_order(tmp_path, monkeypatch):
    monkeypatch.delenv("VALIDATE", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "nowhere"))
    monkeypatch.setenv("ORACLES_DIR", str(tmp_path))
    assert oracles.validate_bin() is None
    built = tmp_path / "VAL" / "build" / "bin"
    built.mkdir(parents=True)
    script(built / "Validate", "")
    assert oracles.validate_bin() == str(built / "Validate")
    onpath = tmp_path / "bin"
    onpath.mkdir()
    script(onpath / "inval", "")
    monkeypatch.setenv("PATH", str(onpath))
    assert oracles.inval_bin() == str(onpath / "inval")
    monkeypatch.setenv("FAST_DOWNWARD", "/opt/fd/fast-downward.py")
    assert oracles.fast_downward_bin() == "/opt/fd/fast-downward.py"


def test_relative_paths_resolve(tmp_path, monkeypatch):
    """FD runs with a temporary cwd, so a discovered relative path must come
    back absolute and still run (review on #155)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FAST_DOWNWARD", raising=False)
    monkeypatch.setenv("ORACLES_DIR", ".oracles")
    (tmp_path / ".oracles" / "downward").mkdir(parents=True)
    script(tmp_path / ".oracles" / "downward" / "fast-downward.py", FAKE_FD)
    fd = oracles.fast_downward_bin()
    assert fd == str(tmp_path / ".oracles" / "downward" / "fast-downward.py")
    monkeypatch.setenv("FAKE_CODE", "0")
    assert oracles.fd_translate(fd, DOMAIN, PROBLEM, 10) == 0
    monkeypatch.setenv("FAST_DOWNWARD", ".oracles/downward/fast-downward.py")
    assert oracles.fast_downward_bin() == fd
    monkeypatch.setenv("FAST_DOWNWARD", "python3")
    assert os.path.isabs(oracles.fast_downward_bin())


def test_plan_steps_for_durative_actions():
    """Durative actions live in their own operator table (review on #155)."""
    from pddlpy import DomainProblem
    from pddlpy.planning import get
    corpus = os.path.join(os.path.dirname(IPC), "durative-action-")
    dp = DomainProblem(corpus + "domain.pddl", corpus + "problem.pddl")
    plan = get("temporal").solve(dp)
    assert oracles.plan_steps(dp, [s.action for s in plan.steps]) == [("go", ("a", "b"))]


def test_fd_translate_and_solve(tmp_path, monkeypatch):
    fd = script(tmp_path / "fast-downward.py", FAKE_FD)
    monkeypatch.setenv("FAKE_CODE", "31")
    assert oracles.fd_translate(fd, DOMAIN, PROBLEM, 10) == 31
    for code in ("20", "21"):  # translator out of memory / time: no verdict
        monkeypatch.setenv("FAKE_CODE", code)
        assert oracles.fd_translate(fd, DOMAIN, PROBLEM, 10) is None
    monkeypatch.setenv("FAKE_CODE", "0")
    monkeypatch.setenv("FAKE_PLAN", "(move rooma roomb)\n; cost = 1 (unit cost)\n")
    assert oracles.fd_solve(fd, DOMAIN, PROBLEM, 10) == (0, [("move", ("rooma", "roomb"))])
    monkeypatch.delenv("FAKE_PLAN")
    monkeypatch.setenv("FAKE_CODE", "11")
    assert oracles.fd_solve(fd, DOMAIN, PROBLEM, 10) == (11, None)
    monkeypatch.setenv("FAKE_SLEEP", "1")
    monkeypatch.setattr(oracles, "FD_GRACE", 0)
    assert oracles.fd_translate(fd, DOMAIN, PROBLEM, 0.5) is None


def test_val_verdict(tmp_path):
    ok = script(tmp_path / "ok", 'print("Plan executed successfully - checking goal\\nPlan valid")')
    bad = script(tmp_path / "bad", 'print("Goal not satisfied\\nPlan invalid"); sys.exit(1)')
    slow = script(tmp_path / "slow", "time.sleep(5)")
    assert oracles.val(ok, DOMAIN, PROBLEM, PLAN, 10) is True
    assert oracles.val(bad, DOMAIN, PROBLEM, PLAN, 10) is False
    assert oracles.val(slow, DOMAIN, PROBLEM, PLAN, 0.5) is None
    assert oracles.val_log(bad, DOMAIN, PROBLEM, PLAN, 10) == \
        "VAL exit 1: Goal not satisfied | Plan invalid"
    assert oracles.val_log(slow, DOMAIN, PROBLEM, PLAN, 0.5) == "VAL timed out"


def test_inval_verdict(tmp_path):
    ok = script(tmp_path / "ok", 'print("plan p01.plan: valid, value: 11 (11 actions, 11 steps)")')
    bad = script(tmp_path / "bad", 'print("plan p01.plan: not valid, value: nil (2 actions)")')
    err = script(tmp_path / "err", 'print("error reading domain")')
    slow = script(tmp_path / "slow", "time.sleep(5)")
    assert oracles.inval(ok, DOMAIN, PROBLEM, PLAN, 10) is True
    assert oracles.inval(bad, DOMAIN, PROBLEM, PLAN, 10) is False
    assert oracles.inval(err, DOMAIN, PROBLEM, PLAN, 10) is False
    assert oracles.inval(slow, DOMAIN, PROBLEM, PLAN, 0.5) is None


def test_read_plan_formats(tmp_path):
    path = tmp_path / "plan"
    path.write_text("; header\n(a x y)\n0.000: (b z) [1.000]\n  (c)\n; (d)\n")
    assert oracles.read_plan(str(path)) == [("a", ("x", "y")), ("b", ("z",)), ("c", ())]
    out = tmp_path / "out"
    oracles.write_plan([("a", ("x", "y")), ("c", ())], str(out))
    assert out.read_text() == "(a x y)\n(c)\n"


def test_requirements():
    assert oracles.declared_requirements(DOMAIN) == []
    assert oracles.fd_supports(DOMAIN)
    adl = os.path.join(IPC, "logistics-round-1-adl", "domain.pddl")
    assert oracles.declared_requirements(adl) == [":adl", ":domain-axioms"]
    assert not oracles.fd_supports(adl)


def test_replay_is_case_insensitive():
    from pddlpy import DomainProblem
    steps = [(n.upper(), tuple(a.upper() for a in args)) for n, args in oracles.read_plan(PLAN)]
    assert oracles.replay(DomainProblem(DOMAIN, PROBLEM), steps) is None
