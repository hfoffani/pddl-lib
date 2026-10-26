"""pddlpy against external oracles (#153): ``make oracle``.

Marked ``oracle`` and deselected from the default run. Each check skips
when its tool is missing (see tests/oracles.py). Pairs: the committed IPC
subset plus tests/corpus/oracle/, or, with ``ORACLE_CORPORA=1``, the full
corpora under ``CORPORA_DIR`` (``DOMAIN`` filters).

  - FD's translator and pddlpy accept and reject the same files;
  - every plan FD finds replays in pddlpy and passes VAL;
  - every plan pddlpy's planners return passes VAL;
  - FD and pddlpy agree on solvable vs unsolvable;
  - the plan fixtures are what they claim, per VAL and INVAL.

Grounded operator counts are not compared: FD's translator prunes by
reachability. ``ORACLE_TIMEOUT`` (default 60) bounds each tool call.
"""
import functools
import os
import signal

import pytest
from corpora_run import discover, per_domain
from golden import IPC, pairs
from oracles import (
    FD_SEARCH_UNSOLVABLE,
    FD_SUCCESS,
    FD_TRANSLATE_UNSOLVABLE,
    declared_requirements,
    fast_downward_bin,
    fd_solve,
    fd_supports,
    fd_translate,
    inval,
    inval_bin,
    plan_steps,
    read_plan,
    replay,
    val,
    validate_bin,
    write_plan,
)
from plans import corruptions, fixtures

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, get

pytestmark = pytest.mark.oracle

TIMEOUT = float(os.environ.get("ORACLE_TIMEOUT") or 60)
ORACLE = os.path.join(os.path.dirname(__file__), "corpus", "oracle")

# Known disagreements on the committed pairs, by (check, domain directory);
# strict xfails, so a fix shows up as XPASS. Checks: accept, fd_plan,
# pddlpy_plan, solvable.
DERIVED = "(:derived ...) does not parse (#141)"
CASE = "identifiers are case-sensitive: (CLEAR c) vs (clear ?x) (#157)"
GOALS = "forall goal is misread (#138)"
KNOWN = {
    ("accept", "psr-middle-derived-predicates-adl"): DERIVED,
    ("fd_plan", "psr-middle-derived-predicates-adl"): DERIVED,
    ("fd_plan", "blocks-strips-typed"): CASE,
    ("solvable", "blocks-strips-typed"): CASE,
    ("fd_plan", "elevator-adl-full-typed"): GOALS,
    ("solvable", "elevator-adl-full-typed"): GOALS,
}


def _pairs():
    if os.environ.get("ORACLE_CORPORA"):
        corpora = os.environ.get("CORPORA_DIR") or ".corpora"
        return [(d, p, os.path.relpath(p, corpora))
                for _, d, p in discover(corpora, os.environ.get("DOMAIN"), per_domain())]
    committed = pairs() + [
        (os.path.join(ORACLE, name, "domain.pddl"), os.path.join(ORACLE, name, "p01.pddl"))
        for name in sorted(os.listdir(ORACLE))
    ]
    return [(d, p, os.path.relpath(p, IPC) if p.startswith(IPC) else os.path.relpath(p, ORACLE))
            for d, p in committed]


PAIRS = _pairs()


def params(check):
    """The pairs for one check, with its KNOWN disagreements as strict xfails."""
    out = []
    for d, p, pid in PAIRS:
        reason = KNOWN.get((check, os.path.dirname(pid)))
        marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
        out.append(pytest.param(d, p, id=pid, marks=marks))
    return out


def need(path, what):
    if path is None:
        pytest.skip("%s not found; run `make oracles` or set its env var" % what)
    return path


@functools.lru_cache(maxsize=None)
def pddlpy_accepts(domain, problem):
    try:
        DomainProblem(domain, problem)
    except Exception:
        return False
    return not any(i["check"] == "syntax" for i in diagnose(domain, problem)["issues"])


@functools.lru_cache(maxsize=None)
def fd_result(domain, problem):
    return fd_solve(need(fast_downward_bin(), "Fast Downward"), domain, problem, TIMEOUT)


class _Timeout(BaseException):  # not swallowed by `except Exception`
    pass


def _alarm(*_):
    raise _Timeout()


@functools.lru_cache(maxsize=None)
def pddlpy_plan(domain, problem):
    """``(planner, plan)``; plan ``None`` if unsolvable. Skips when pddlpy
    cannot load the pair, refuses it, or runs out of time."""
    if not pddlpy_accepts(domain, problem):
        pytest.skip("pddlpy rejects the pair")
    dp = DomainProblem(domain, problem)
    planner = "temporal" if dp.durative_operators() else "astar"
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(TIMEOUT))
    try:
        return planner, get(planner).solve(dp)
    except PlannerError as exc:
        pytest.skip("pddlpy refuses: %s" % exc)
    except _Timeout:
        pytest.skip("pddlpy timed out")
    except MemoryError:
        pytest.skip("pddlpy ran out of memory (ORACLE_MEMORY_MB)")
    finally:
        signal.alarm(0)


@pytest.fixture(autouse=True, scope="module")
def memory_cap():
    """With ``ORACLE_MEMORY_MB`` set, cap this process's address space, so a
    runaway pddlpy search raises MemoryError instead of exhausting the
    machine (it took a CI runner down). Linux only: macOS ignores it."""
    mb = int(os.environ.get("ORACLE_MEMORY_MB") or 0)
    if not mb:
        yield
        return
    import resource
    old = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (mb * 1024 * 1024, old[1]))
    yield
    resource.setrlimit(resource.RLIMIT_AS, old)


def fd_only(domain):
    if not fd_supports(domain):
        pytest.skip("outside FD's fragment: %s" % declared_requirements(domain))


@pytest.mark.parametrize("domain,problem", params("accept"))
def test_accept_reject_agrees_with_fd(domain, problem):
    fd_only(domain)
    code = fd_translate(need(fast_downward_bin(), "Fast Downward"), domain, problem, TIMEOUT)
    if code is None:
        pytest.skip("FD translator timed out")
    fd_accepts = code in (FD_SUCCESS, FD_TRANSLATE_UNSOLVABLE)
    assert pddlpy_accepts(domain, problem) == fd_accepts, "FD translator exit %d" % code


@pytest.mark.parametrize("domain,problem", params("fd_plan"))
def test_fd_plan_replays_in_pddlpy_and_val(domain, problem, tmp_path):
    fd_only(domain)
    code, steps = fd_result(domain, problem)
    if steps is None:
        pytest.skip("FD found no plan (exit %s)" % code)
    plan_file = str(tmp_path / "plan")
    write_plan(steps, plan_file)
    assert val(need(validate_bin(), "VAL"), domain, problem, plan_file, TIMEOUT) is True
    assert pddlpy_accepts(domain, problem), "pddlpy rejects a pair FD solves"
    assert replay(DomainProblem(domain, problem), steps) is None


@pytest.mark.parametrize("domain,problem", params("pddlpy_plan"))
def test_pddlpy_plan_passes_val(domain, problem, tmp_path):
    validate = need(validate_bin(), "VAL")
    planner, plan = pddlpy_plan(domain, problem)
    if plan is None:
        pytest.skip("pddlpy found no plan")
    plan_file = str(tmp_path / "plan")
    dp = DomainProblem(domain, problem)
    if planner == "temporal":
        with open(plan_file, "w", encoding="utf-8") as f:
            for s in plan.steps:
                name, args = plan_steps(dp, [s.action])[0]
                f.write("%.3f: (%s) [%.3f]\n" % (s.start, " ".join((name,) + args), s.duration))
    else:
        write_plan(plan_steps(dp, plan), plan_file)
    assert val(validate, domain, problem, plan_file, TIMEOUT) is True


@pytest.mark.parametrize("domain,problem", params("solvable"))
def test_solvability_agrees_with_fd(domain, problem):
    fd_only(domain)
    code, _ = fd_result(domain, problem)
    if code in (FD_SUCCESS,):
        fd_solvable = True
    elif code in (FD_TRANSLATE_UNSOLVABLE, FD_SEARCH_UNSOLVABLE):
        fd_solvable = False
    else:
        pytest.skip("FD gave no verdict (exit %s)" % code)
    _, plan = pddlpy_plan(domain, problem)
    assert (plan is not None) == fd_solvable


@pytest.mark.parametrize("plan", fixtures(), ids=lambda p: os.path.relpath(p, IPC))
@pytest.mark.parametrize("tool", ["VAL", "INVAL"])
def test_plan_fixtures_per_validator(plan, tool):
    binary = need(validate_bin() if tool == "VAL" else inval_bin(), tool)
    check = val if tool == "VAL" else inval
    root = os.path.dirname(os.path.dirname(plan))
    stem = os.path.basename(plan).split(".")[0]
    domain, problem = os.path.join(root, "domain.pddl"), os.path.join(root, stem + ".pddl")
    assert check(binary, domain, problem, plan, TIMEOUT) is True
    for kind in corruptions(read_plan(plan)):
        bad = plan[: -len(".plan")] + ".%s.plan" % kind
        assert check(binary, domain, problem, bad, TIMEOUT) is False, kind
