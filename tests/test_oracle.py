"""pddlpy against external oracles (#153): ``make oracle``.

Marked ``oracle`` and deselected from the default run. Each check skips
when its tool is missing (see tests/oracles.py). Pairs: the committed IPC
subset plus tests/corpus/oracle/, or, with ``ORACLE_CORPORA=1``, the full
corpora under ``CORPORA_DIR`` (``DOMAIN`` filters, ``CORPORA_PER_DOMAIN``
samples). ``ORACLE_SHARD=i/n`` keeps every n-th pair from the i-th, so CI
can split a corpus across jobs.

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
import sys
import tempfile

import pytest
from corpora_run import discover, per_domain
from golden import IPC, pairs
from oracles import (
    FD_ACCEPTS,
    FD_REJECTS,
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
    val_log,
    val_verdict_log,
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


def shard(items, spec):
    """``spec`` 'i/n' keeps items i, i+n, i+2n, ...; empty keeps all."""
    if not spec:
        return items
    i, n = (int(x) for x in spec.split("/"))
    return items[i::n]


PAIRS = shard(_pairs(), os.environ.get("ORACLE_SHARD"))


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
def fd_result(domain, problem):
    return fd_solve(need(fast_downward_bin(), "Fast Downward"), domain, problem, TIMEOUT)


class _Timeout(BaseException):  # not swallowed by `except Exception`
    pass


def _alarm(*_):
    raise _Timeout()


def bounded(fn, *args):
    """Run pddlpy work under ``ORACLE_TIMEOUT`` and the memory cap. Returns
    ``(None, result)``, or ``(reason, None)`` when it ran out of either.
    Every pddlpy call goes through here: one unbounded load, grounding or
    search stalled a CI job for hours."""
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(TIMEOUT))
    try:
        return None, fn(*args)
    except _Timeout:
        return "pddlpy timed out", None
    except MemoryError:
        return "pddlpy ran out of memory (ORACLE_MEMORY_MB)", None
    finally:
        signal.alarm(0)


def _accepts(domain, problem):
    try:
        DomainProblem(domain, problem)
    except Exception:
        return False
    return not any(i["check"] == "syntax" for i in diagnose(domain, problem)["issues"])


def _solve(domain, problem):
    dp = DomainProblem(domain, problem)
    planner = "temporal" if dp.durative_operators() else "astar"
    try:
        return planner, get(planner).solve(dp)
    except PlannerError as exc:
        return planner, exc


# Outcomes are cached, timeouts included, so the checks sharing a pair do
# not each wait out the same deadline.
@functools.lru_cache(maxsize=None)
def _accepts_outcome(domain, problem):
    return bounded(_accepts, domain, problem)


@functools.lru_cache(maxsize=None)
def _solve_outcome(domain, problem):
    return bounded(_solve, domain, problem)


def pddlpy_accepts(domain, problem):
    """Whether pddlpy loads the pair without syntax errors; skips the
    calling check when that cannot be decided in time."""
    reason, accepted = _accepts_outcome(domain, problem)
    if reason:
        pytest.skip(reason)
    return accepted


def pddlpy_plan(domain, problem):
    """``(planner, plan)``; plan ``None`` if unsolvable. Skips when pddlpy
    cannot load the pair, refuses it, or runs out of time or memory."""
    if not pddlpy_accepts(domain, problem):
        pytest.skip("pddlpy rejects the pair")
    reason, result = _solve_outcome(domain, problem)
    if reason:
        pytest.skip(reason)
    planner, plan = result
    if isinstance(plan, PlannerError):
        pytest.skip("pddlpy refuses: %s" % plan)
    return planner, plan


@pytest.fixture(autouse=True, scope="module")
def memory_cap():
    """With ``ORACLE_MEMORY_MB`` set, cap this process's address space, so a
    runaway pddlpy search raises MemoryError instead of exhausting the
    machine (it took a CI runner down). Linux only: elsewhere (macOS) the setting is ignored."""
    mb = int(os.environ.get("ORACLE_MEMORY_MB") or 0)
    if not mb or not sys.platform.startswith("linux"):
        yield
        return
    import resource
    old = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (mb * 1024 * 1024, old[1]))
    yield
    resource.setrlimit(resource.RLIMIT_AS, old)


def assert_val_valid(validate, domain, problem, plan_file):
    """VAL accepts the plan; skips when VAL could not read the domain or
    problem, or when VAL also rejects Fast Downward's plan for the pair (the
    oracles disagree, e.g. movie), and otherwise fails with VAL's reason."""
    verdict = val(validate, domain, problem, plan_file, TIMEOUT)
    if verdict is None:
        pytest.skip("VAL gave no verdict: %s" % val_log(validate, domain, problem,
                                                         plan_file, TIMEOUT))
    if not verdict:
        disagreement = val_rejects_fd_plan(validate, domain, problem)
        if disagreement:
            pytest.skip("oracles disagree: VAL rejects FD's plan too: %s" % disagreement)
    assert verdict, val_log(validate, domain, problem, plan_file, TIMEOUT)


@functools.lru_cache(maxsize=None)
def val_rejects_fd_plan(validate, domain, problem):
    """VAL's reason for rejecting Fast Downward's plan for the pair, or
    ``None`` when it accepts it or there is no FD plan to judge."""
    if fast_downward_bin() is None or not fd_supports(domain):
        return None
    _, steps = fd_result(domain, problem)
    if steps is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        plan_file = os.path.join(tmp, "fd.plan")
        write_plan(steps, plan_file)
        if val(validate, domain, problem, plan_file, TIMEOUT) is not False:
            return None
        return val_log(validate, domain, problem, plan_file, TIMEOUT)


def fd_only(domain):
    if not fd_supports(domain):
        pytest.skip("outside FD's fragment: %s" % declared_requirements(domain))


@pytest.mark.parametrize("domain,problem", params("accept"))
def test_accept_reject_agrees_with_fd(domain, problem):
    fd_only(domain)
    code = fd_translate(need(fast_downward_bin(), "Fast Downward"), domain, problem, TIMEOUT)
    if code is None:
        pytest.skip("FD translator ran out of time or memory")
    if code not in FD_ACCEPTS | FD_REJECTS:
        pytest.skip("FD translator gave no verdict (exit %d)" % code)
    fd_accepts = code in FD_ACCEPTS
    assert pddlpy_accepts(domain, problem) == fd_accepts, "FD translator exit %d" % code


@pytest.mark.parametrize("domain,problem", params("fd_plan"))
def test_fd_plan_replays_in_pddlpy_and_val(domain, problem, tmp_path):
    fd_only(domain)
    code, steps = fd_result(domain, problem)
    if steps is None:
        pytest.skip("FD found no plan (exit %s)" % code)
    plan_file = str(tmp_path / "plan")
    write_plan(steps, plan_file)
    validate = need(validate_bin(), "VAL")
    assert_val_valid(validate, domain, problem, plan_file)
    assert pddlpy_accepts(domain, problem), "pddlpy rejects a pair FD solves"
    reason, failure = bounded(lambda: replay(DomainProblem(domain, problem), steps))
    if reason:
        pytest.skip(reason)
    assert failure is None


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
    assert_val_valid(validate, domain, problem, plan_file)


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
        assert check(binary, domain, problem, bad, TIMEOUT) is False, "%s: %s" % (
            kind, val_verdict_log(binary, domain, problem, bad, TIMEOUT) if tool == "VAL" else "")
