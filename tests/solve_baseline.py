"""Solve baseline (M2): ``make baseline``.

Runs pddlpy's planners and Fast Downward over the sampled IPC corpora
(``make corpora``) and writes one CSV row per (pair, planner), plus a
Markdown summary. It measures; it is not a gate.

Every run is a subprocess in its own process group with a wall-clock and a
resident-memory cap, so a runaway search cannot take the machine down (FD's
own memory limit does not work on macOS). pddlpy runs report the phase they
were in (parse, ground, search, validate), and the seconds spent in each, so
a timeout says where the time went.

Rows already in the CSV are skipped, so an interrupted run resumes where it
stopped. The default output directory names the time limit and the sample
size, so runs with other settings do not mix.

Runners:
  bfs, ucs, astar  pddlpy's planners (every pair)
  temporal         pddlpy's sequential temporal planner (durative pairs)
  validate         ``validate_plan`` on an empty plan: does the plan
                   validator accept the domain at all? (durative pairs)
  fd-opt           Fast Downward ``astar(lmcut())``
  fd-sat           Fast Downward ``--alias lama-first``

Environment:
  CORPORA_DIR         corpora root (default .corpora)
  DOMAIN              only pairs whose path contains this substring
  CORPORA_PER_DOMAIN  the first N problems of each domain variant
  BASELINE_TIMEOUT    seconds per run (default 10)
  BASELINE_MEMORY_GB  resident memory per run (default 3)
  BASELINE_JOBS       runs in parallel (default 4)
  BASELINE_RUNNERS    comma-separated subset of the runners above
  BASELINE_OUT        output directory (default
                      $CORPORA_DIR/results/baseline-t<timeout>-n<per domain>)

``python tests/solve_baseline.py --summary CSV`` rewrites the summary only.
"""
from __future__ import annotations

import collections
import contextlib
import csv
import io
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

START = time.monotonic()

from corpora_run import Pair, _variant, discover, per_domain  # noqa: E402
from oracles import _command, fast_downward_bin, read_plan_cost  # noqa: E402

PDDLPY = ("bfs", "ucs", "astar")
DURATIVE_ONLY = ("temporal", "validate")
FD_CONFIGS = {
    "fd-opt": ([], ["--search", "astar(lmcut())"]),
    "fd-sat": (["--alias", "lama-first"], []),
}
RUNNERS = PDDLPY + DURATIVE_ONLY + tuple(FD_CONFIGS)

FIELDS = ["corpus", "variant", "domain", "problem", "runner", "status", "phase",
          "cost", "length", "expansions", "parse_s", "ground_s", "search_s",
          "total_s", "validated", "message"]

#: Fast Downward exit codes (driver/returncodes.py) -> status.
FD_STATUS = {0: "solved", 10: "unsolvable", 11: "unsolvable", 12: "limit",
             20: "memout", 21: "timeout", 22: "memout", 23: "timeout",
             24: "memout", 30: "refused", 31: "refused", 34: "refused"}
#: Seconds past the time limit before the process group is killed, so the
#: planner's own limit fires first and reports.
GRACE = 5
POLL = 0.5


# -- running one subprocess under limits ------------------------------------

def group_rss(pgid: int) -> int:
    """Resident bytes of every process in group ``pgid``."""
    out = subprocess.run(["ps", "-A", "-o", "pgid=,rss="], capture_output=True,
                         text=True).stdout
    kb = sum(int(rss) for g, rss in (line.split() for line in out.splitlines()
                                     if line.strip()) if int(g) == pgid)
    return kb * 1024


def run_limited(cmd: Sequence[str], timeout: float, memory: int,
                cwd: Optional[str] = None) -> Tuple[Optional[int], str, Optional[str], float]:
    """Run ``cmd`` in a new process group. Returns ``(exit code, stdout,
    reason, seconds)``; ``reason`` is ``timeout`` or ``memout`` when the
    group was killed, and the code is then ``None``."""
    t0 = time.monotonic()
    proc = subprocess.Popen(list(cmd), cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            start_new_session=True)
    reason = None
    while True:
        try:
            out, _ = proc.communicate(timeout=POLL)
            break
        except subprocess.TimeoutExpired:
            if time.monotonic() - t0 > timeout:
                reason = "timeout"
            elif group_rss(proc.pid) > memory:
                reason = "memout"
            if reason:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGKILL)
                out, _ = proc.communicate()
                break
    code = None if reason else proc.returncode
    return code, out, reason, time.monotonic() - t0


# -- the pddlpy child -------------------------------------------------------

def _emit(**fields: Any) -> None:
    print(json.dumps(fields), flush=True)


def child(runner: str, domain: str, problem: str, budget: float) -> None:
    """Run one pddlpy runner and print its progress as JSON lines: a
    ``phase`` line as each phase starts, its seconds as it ends, and a final
    ``status``. The parent merges the lines, so a killed run still shows the
    phase it was in."""
    from pddlpy import DomainProblem
    from pddlpy.planning import get
    from pddlpy.planning.base import PlannerError, SearchLimitError
    from pddlpy.planning.solving import plan_steps
    from pddlpy.planning.validation import PlanValidationError, check_supported, validate_plan

    _emit(phase="parse")
    t = time.monotonic()
    # ANTLR prints syntax errors to stderr; the status line carries enough.
    with contextlib.redirect_stderr(io.StringIO()):
        dp = DomainProblem(domain, problem)
    _emit(parse_s=time.monotonic() - t)

    if runner == "validate":
        _emit(phase="validate")
        try:
            check_supported(dp)
        except PlanValidationError as exc:
            _emit(status="refused", message=str(exc))
            return
        bad = [n for n, op in dp.domain.durative_operators.items()
               if not op.simple or op.continuous]
        if bad:
            with open(domain, encoding="utf-8", errors="replace") as f:
                found = durative_causes(f.read(), bad)
            _emit(status="refused", message="durative actions with %s parts"
                  % " + ".join(sorted(found)))
            return
        _emit(status="accepted")
        return

    solver = get(runner)
    start_search = solver._start_search
    searching: List[float] = []

    def timed_start() -> None:
        # Every search planner calls _start_search once the task is built:
        # what came before is grounding (and the requirement checks).
        searching.append(time.monotonic())
        # The search gets what is left of the budget, and stops by itself
        # (SearchLimitError) before the parent kills it.
        solver.timeout = max(budget - (time.monotonic() - START), 0.01)
        _emit(ground_s=searching[0] - t, phase="search")
        start_search()

    def search_s() -> float:
        return time.monotonic() - searching[0] if searching else 0.0

    solver._start_search = timed_start  # type: ignore[method-assign]
    _emit(phase="ground")
    t = time.monotonic()
    try:
        plan = solver.solve(dp)
    except SearchLimitError as exc:
        _emit(status="limit", search_s=search_s(), expansions=solver._expanded,
              message=str(exc))
        return
    except PlannerError as exc:
        _emit(status="error" if searching else "refused", message=str(exc))
        return
    search = dict(search_s=search_s(), expansions=solver._expanded)
    if plan is None:
        if solver.complete:
            _emit(status="unsolvable", **search)
        else:
            _emit(status="limit", message="incomplete planner exhausted", **search)
        return
    _emit(phase="validate", **search)
    try:
        result = validate_plan(dp, plan_steps(dp, plan))
    except PlanValidationError as exc:
        _emit(status="solved", validated=False, cost=plan.cost, length=len(plan),
              message="not validated: %s" % exc)
        return
    status = "solved" if result.valid else "invalid"
    _emit(status=status, validated=True, cost=plan.cost, length=len(plan),
          message="" if result.valid else result.failure.message)  # type: ignore[union-attr]


#: What makes a durative action unsimple, read from its text. A textual
#: check is enough to sort refusals into causes; pddlpy only records
#: ``simple`` and ``continuous`` per action.
_CAUSES = [
    ("continuous", re.compile(r"#t\b")),
    ("duration-expression", re.compile(r":duration\s*\((and\s*\()?\s*[<>=]+\s*\?duration\s*\(")),
    ("equality", re.compile(r"\(\s*=\s*\?(?!duration\b)")),
    ("conditional", re.compile(r"\(\s*when\b")),
    ("quantified", re.compile(r"\(\s*(forall|exists)\b")),
    ("numeric", re.compile(r"\(\s*(increase|decrease|assign|scale-up|scale-down"
                           r"|(?:<=|>=|<|>)(?!=)(?!\s*\?duration)|=\s*\()")),
]


def _block(text: str, start: int) -> str:
    """The balanced parenthesized form starting at ``text[start]``."""
    depth = 0
    for i in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            return text[start:i + 1]
    return text[start:]


def durative_causes(text: str, names: Iterable[str]) -> set:
    """The causes found in the ``(:durative-action NAME ...)`` forms of
    ``text``; ``other`` when none matches."""
    text = re.sub(r";[^\n]*", "", text.lower())
    found = set()
    for name in names:
        m = re.search(r"\(\s*:durative-action\s+%s\b" % re.escape(name.lower()), text)
        if not m:
            continue
        body = _block(text, m.start())
        hits = {c for c, rx in _CAUSES if rx.search(body)}
        found |= hits or {"other"}
    return found or {"other"}


def merge(out: str) -> Dict[str, Any]:
    """The child's JSON lines as one dict; later lines win."""
    row: Dict[str, Any] = {}
    for line in out.splitlines():
        with contextlib.suppress(ValueError):
            row.update(json.loads(line))
    return row


def pddlpy_row(runner: str, domain: str, problem: str, timeout: float,
               memory: int) -> Dict[str, Any]:
    cmd = [sys.executable, os.path.abspath(__file__), "--child", runner,
           domain, problem, str(timeout)]
    code, out, reason, seconds = run_limited(cmd, timeout + GRACE, memory)
    row = merge(out)
    if reason:
        row["status"] = reason
    elif "status" not in row:
        row["status"] = "error"
        row["message"] = "child exited %s" % code
    row["total_s"] = seconds
    return row


# -- Fast Downward ----------------------------------------------------------

_EXPANDED = re.compile(r"Expanded (\d+) state")


def fd_row(fd: str, runner: str, domain: str, problem: str, timeout: float,
           memory: int) -> Dict[str, Any]:
    before, after = FD_CONFIGS[runner]
    with tempfile.TemporaryDirectory() as tmp:
        plan_file = os.path.join(tmp, "plan")
        cmd = (_command(fd) + before
               + ["--overall-time-limit", "%ds" % max(1, int(timeout)),
                  "--plan-file", plan_file,
                  os.path.abspath(domain), os.path.abspath(problem)] + after)
        code, out, reason, seconds = run_limited(cmd, timeout + GRACE, memory, cwd=tmp)
        cost = read_plan_cost(plan_file) if os.path.exists(plan_file) else None
    row: Dict[str, Any] = {"total_s": seconds}
    row["status"] = reason or FD_STATUS.get(code, "error")  # type: ignore[arg-type]
    if code:
        row["message"] = "exit %s" % code
    if cost is not None:
        row["cost"] = cost[0]
    found = _EXPANDED.findall(out)
    if found:
        row["expansions"] = int(found[-1])
    return row


# -- the run ----------------------------------------------------------------

def is_durative(domain: str) -> bool:
    with open(domain, encoding="utf-8", errors="replace") as f:
        return ":durative-action" in f.read().lower()


def tasks(pairs: Iterable[Pair], runners: Sequence[str]) -> List[Tuple[Pair, str]]:
    work = []
    for pair in pairs:
        durative = is_durative(pair[1])
        for r in runners:
            if r in DURATIVE_ONLY and not durative:
                continue
            work.append((pair, r))
    return work


def done(path: str) -> set:
    """``(problem, runner)`` keys already in the CSV."""
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {(r["problem"], r["runner"]) for r in csv.DictReader(f)}


def run_one(pair: Pair, runner: str, corpora: str, fd: Optional[str],
            timeout: float, memory: int) -> Dict[str, Any]:
    corpus, dom, prob = pair
    if runner in FD_CONFIGS:
        row = (fd_row(fd, runner, dom, prob, timeout, memory) if fd
               else {"status": "missing", "message": "Fast Downward not found"})
    else:
        row = pddlpy_row(runner, dom, prob, timeout, memory)
    row.update(corpus=corpus, variant=os.path.relpath(_variant(pair), corpora),
               domain=os.path.relpath(dom, corpora),
               problem=os.path.relpath(prob, corpora), runner=runner)
    if row["status"] not in ("timeout", "memout"):
        row.pop("phase", None)
    return row


def out_dir(corpora: str, timeout: float) -> str:
    return os.environ.get("BASELINE_OUT") or os.path.join(
        corpora, "results", "baseline-t%g-n%s" % (timeout, per_domain() or "all"))


def main() -> int:
    corpora = os.environ.get("CORPORA_DIR") or ".corpora"
    timeout = float(os.environ.get("BASELINE_TIMEOUT") or 10)
    memory = int(float(os.environ.get("BASELINE_MEMORY_GB") or 3) * 2**30)
    jobs = int(os.environ.get("BASELINE_JOBS") or 4)
    runners = [r for r in (os.environ.get("BASELINE_RUNNERS") or ",".join(RUNNERS)).split(",") if r]
    unknown = set(runners) - set(RUNNERS)
    if unknown:
        print("baseline: unknown runners %s; pick from %s" % (sorted(unknown), ", ".join(RUNNERS)))
        return 2
    pairs = discover(corpora, os.environ.get("DOMAIN"), per_domain())
    if not pairs:
        print("baseline: no domain/problem pairs under %r; run `make corpora` "
              "first (or set CORPORA_DIR / DOMAIN). Nothing to do." % corpora)
        return 0
    out = out_dir(corpora, timeout)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, "baseline.csv")
    seen = done(path)
    work = [(p, r) for p, r in tasks(pairs, runners)
            if (os.path.relpath(p[2], corpora), r) not in seen]
    fd = fast_downward_bin()
    print("baseline: %d pairs, %d runs left (%d done) -> %s" % (
        len(pairs), len(work), len(seen), path), flush=True)
    if not fd and any(r in FD_CONFIGS for r in runners):
        print("baseline: Fast Downward not found (make oracles); its rows say 'missing'")

    lock = threading.Lock()
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        if new:
            writer.writeheader()

        def job(item: Tuple[Pair, str]) -> None:
            row = run_one(item[0], item[1], corpora, fd, timeout, memory)
            with lock:
                writer.writerow({k: _cell(row.get(k)) for k in FIELDS})
                f.flush()
                job.n += 1  # type: ignore[attr-defined]
                if job.n % 50 == 0 or job.n == len(work):  # type: ignore[attr-defined]
                    print("  %d/%d" % (job.n, len(work)), flush=True)  # type: ignore[attr-defined]

        job.n = 0  # type: ignore[attr-defined]
        with ThreadPoolExecutor(jobs) as pool:
            list(pool.map(job, work))
    write_summary(path)
    print("baseline: summary in %s" % os.path.join(out, "summary.md"))
    return 0


def _cell(v: Any) -> Any:
    if isinstance(v, float):
        return "%.4g" % v
    if v is None:
        return ""
    return v


# -- the summary ------------------------------------------------------------

def load(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _table(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> List[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return lines


def _f(row: Dict[str, str], key: str) -> Optional[float]:
    return float(row[key]) if row.get(key) else None


def _median(xs: List[float]) -> str:
    return "%.3g" % statistics.median(xs) if xs else "-"


#: Refusal messages grouped by cause: the text up to the first specific name.
_SPECIFIC = [(re.compile(r"\b\w+Planner\b"), "planner"),
             (re.compile(r"action '[^']*'"), "action 'X'"),
             (re.compile(r"; \S+ has"), "; X has")]


def cause(message: str) -> str:
    """A refusal message without the names that vary per domain."""
    for rx, repl in _SPECIFIC:
        message = rx.sub(repl, message)
    return message


def summary(rows: List[Dict[str, str]]) -> str:
    runners = [r for r in RUNNERS if any(x["runner"] == r for x in rows)]
    statuses = sorted({x["status"] for x in rows})
    pairs = {x["problem"] for x in rows}
    lines = ["# Solve baseline", "",
             "%d pairs, %d runs. Status counts per runner:" % (len(pairs), len(rows)), ""]
    count = collections.Counter((x["runner"], x["status"]) for x in rows)
    lines += _table(["runner"] + statuses + ["total"],
                    [[r] + [count[r, s] or "" for s in statuses]
                     + [sum(count[r, s] for s in statuses)] for r in runners])

    # Solved by one side only: where pddlpy is behind FD.
    solved = collections.defaultdict(set)
    for x in rows:
        if x["status"] == "solved":
            solved[x["runner"]].add(x["problem"])
    pd = set().union(*(solved[r] for r in PDDLPY))
    fd = solved["fd-opt"] | solved["fd-sat"]
    lines += ["", "Pairs solved: any pddlpy planner %d, any FD configuration %d, "
              "FD only %d, pddlpy only %d." % (len(pd), len(fd), len(fd - pd), len(pd - fd))]

    # Where pddlpy's runs stopped, and where the time went.
    lines += ["", "## pddlpy: where the time goes", "",
              "Phase a run was in when it hit the time or memory limit:", ""]
    killed = [x for x in rows if x["runner"] in PDDLPY + ("temporal",)
              and x["status"] in ("timeout", "memout", "limit")]
    phases = collections.Counter((x["runner"], x["status"],
                                  x["phase"] or "search") for x in killed)
    lines += _table(["runner", "status", "phase", "runs"],
                    [list(k) + [n] for k, n in sorted(phases.items())])
    lines += ["", "Median seconds per phase (runs that reached the search) and "
              "expansions per second:", ""]
    body = []
    for r in runners:
        if r not in PDDLPY + ("temporal",):
            continue
        rs = [x for x in rows if x["runner"] == r and x["ground_s"]]
        rate = [float(x["expansions"]) / float(x["search_s"]) for x in rs
                if x["expansions"] and _f(x, "search_s")]
        body.append([r, len(rs)] + [_median([v for v in (_f(x, k) for x in rs) if v is not None])
                                    for k in ("parse_s", "ground_s", "search_s")]
                    + [_median(rate)])
    lines += _table(["runner", "runs", "parse", "ground", "search", "exp/s"], body)

    # Refusals by cause.
    refused = collections.Counter((x["runner"], cause(x["message"])) for x in rows
                                  if x["status"] == "refused")
    if refused:
        lines += ["", "## Refusals by cause", ""]
        lines += _table(["runner", "cause", "runs"],
                        [[r, c, n] for (r, c), n in sorted(refused.items())])
    errors = [x for x in rows if x["status"] in ("error", "invalid")]
    if errors:
        lines += ["", "## Errors and invalid plans", ""]
        lines += _table(["runner", "problem", "status", "message"],
                        [[x["runner"], x["problem"], x["status"], x["message"][:120]]
                         for x in errors])

    # Coverage per domain variant.
    lines += ["", "## Solved per domain variant", ""]
    by = collections.defaultdict(collections.Counter)
    n = collections.Counter()
    for x in rows:
        if x["runner"] == runners[0]:
            n[x["variant"]] += 1
        if x["status"] == "solved":
            by[x["variant"]][x["runner"]] += 1
    variants = sorted({x["variant"] for x in rows})
    lines += _table(["variant", "pairs"] + runners,
                    [[v, n[v] or ""] + [by[v][r] for r in runners] for v in variants])
    return "\n".join(lines) + "\n"


def write_summary(path: str) -> None:
    with open(os.path.join(os.path.dirname(path), "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary(load(path)))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:
        runner, dom, prob, budget = sys.argv[2:6]
        child(runner, dom, prob, float(budget))
    elif sys.argv[1:2] == ["--summary"]:
        write_summary(sys.argv[2])
    else:
        sys.exit(main())
