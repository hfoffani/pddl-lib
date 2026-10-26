"""Run pddlpy over the full IPC corpora (#153): ``make corpora-test``.

Walks every domain/problem pair under ``CORPORA_DIR`` (fetched by
``make corpora``), takes the same snapshot as the golden check
(tests/golden.py) with a per-pair timeout, and writes one JSON per pair
plus ``summary.json`` under ``CORPORA_OUT``. It is a report, not a gate:
crashes and timeouts are counted, and the exit status is 0. With nothing
fetched it says so and exits 0.

Environment:
  CORPORA_DIR      corpora root (default .corpora)
  CORPORA_OUT      results directory (default $CORPORA_DIR/results)
  DOMAIN           only pairs whose path contains this substring
  CORPORA_TIMEOUT  seconds per pair (default 60)
  CORPORA_JOBS     worker processes (default: CPU count)
"""
from __future__ import annotations

import ast
import collections
import glob
import json
import os
import signal
import sys
from multiprocessing import Pool
from typing import Any, Dict, List, Optional, Tuple

from golden import dumps, snapshot

Pair = Tuple[str, str, str]  # (corpus, domain path, problem path)


def potassco_pairs(root: str) -> List[Pair]:
    """potassco/pddl-instances: ipc-*/domains/<variant>/instances/instance-N.pddl,
    with one domain.pddl or a domains/domain-N.pddl per instance."""
    pairs = []
    for prob in glob.glob(os.path.join(root, "ipc-*", "domains", "*", "instances", "instance-*.pddl")):
        variant = os.path.dirname(os.path.dirname(prob))
        n = os.path.basename(prob)[len("instance-"):]
        dom = os.path.join(variant, "domain.pddl")
        if not os.path.exists(dom):
            dom = os.path.join(variant, "domains", "domain-" + n)
        pairs.append(("potassco", dom, prob))
    return pairs


def classical_pairs(root: str) -> List[Pair]:
    """AI-Planning/classical-domains: each classical/<domain>/api.py lists its
    (domain, problem) pairs. Read as a literal, never imported."""
    base = os.path.join(root, "classical")
    pairs = []
    for api in glob.glob(os.path.join(base, "*", "api.py")):
        with open(api, encoding="utf-8") as f:
            text = f.read()
        domains = ast.literal_eval(text[text.index("=") + 1:].strip())
        for d in domains:
            for dom, prob in d["problems"]:
                pairs.append(("classical", os.path.join(base, dom), os.path.join(base, prob)))
    return pairs


def discover(corpora: str, needle: Optional[str]) -> List[Pair]:
    pairs = []
    if os.path.isdir(os.path.join(corpora, "potassco")):
        pairs += potassco_pairs(os.path.join(corpora, "potassco"))
    if os.path.isdir(os.path.join(corpora, "classical")):
        pairs += classical_pairs(os.path.join(corpora, "classical"))
    if needle:
        pairs = [p for p in pairs if needle in os.path.relpath(p[2], corpora)]
    return sorted(pairs)


class _Timeout(BaseException):
    """Not an ``Exception``: snapshot() records loader and validate
    exceptions as results, and must not swallow the deadline."""


def _alarm(*_: Any) -> None:
    raise _Timeout()


def run_pair(args: Tuple[Pair, str, str, int]) -> Tuple[str, str]:
    """Snapshot one pair into ``out``; return (corpus, status)."""
    (corpus, dom, prob), corpora, out, timeout = args
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout)
    try:
        snap: Dict[str, Any] = snapshot(dom, prob)
        if "error" in snap:
            status = "crash"
        elif snap["validate"].get("valid"):
            status = "valid"
        else:
            status = "issues"
    except _Timeout:
        snap, status = {"timeout": timeout}, "timeout"
    finally:
        signal.alarm(0)
    snap["domain"] = os.path.relpath(dom, corpora)
    snap["problem"] = os.path.relpath(prob, corpora)
    path = os.path.join(out, os.path.splitext(snap["problem"])[0] + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(snap))
    return corpus, status


def main() -> int:
    corpora = os.environ.get("CORPORA_DIR") or ".corpora"
    out = os.environ.get("CORPORA_OUT") or os.path.join(corpora, "results")
    timeout = int(os.environ.get("CORPORA_TIMEOUT") or 60)
    jobs = int(os.environ.get("CORPORA_JOBS") or os.cpu_count() or 1)
    pairs = discover(corpora, os.environ.get("DOMAIN"))
    if not pairs:
        print("corpora-test: no domain/problem pairs under %r; run `make corpora` "
              "first (or set CORPORA_DIR / DOMAIN). Nothing to do." % corpora)
        return 0

    print("corpora-test: %d pairs from %s -> %s" % (len(pairs), corpora, out))
    counts: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    work = [(p, corpora, out, timeout) for p in pairs]
    if jobs == 1:
        results = map(run_pair, work)
    else:
        results = Pool(jobs).imap_unordered(run_pair, work, chunksize=4)
    for corpus, status in results:
        counts[corpus][status] += 1

    summary = {c: dict(sorted(n.items())) for c, n in sorted(counts.items())}
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    for corpus, n in summary.items():
        print("  %-10s %s" % (corpus, "  ".join("%s=%d" % kv for kv in n.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
