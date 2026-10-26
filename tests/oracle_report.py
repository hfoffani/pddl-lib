"""Markdown report of an oracle run (#153), for the oracle workflow.

    python tests/oracle_report.py [--title T] FILE...

Each FILE is a pytest JUnit XML (``make oracle PYTEST_ARGS=--junitxml=...``)
or a ``summary.json`` from ``make corpora-test``. The report counts outcomes
per oracle check and lists each failing pair with the first line of its
message.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

MAX_LISTED = 50  # failures listed per check; the rest are counted


def outcome(case: ET.Element) -> Tuple[str, str]:
    """``(outcome, message)`` of one JUnit testcase."""
    for tag in ("failure", "error"):
        el = case.find(tag)
        if el is not None:
            return "failed", (el.get("message") or el.text or "").strip()
    el = case.find("skipped")
    if el is not None:
        kind = "xfailed" if el.get("type") == "pytest.xfail" else "skipped"
        return kind, (el.get("message") or "").strip()
    return "passed", ""


def junit_section(path: str) -> List[str]:
    counts: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    failures: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    for case in ET.parse(path).getroot().iter("testcase"):
        m = re.match(r"([^\[]+)(?:\[(.*)\])?$", case.get("name", ""))
        check, pair = (m.group(1), m.group(2) or "") if m else (case.get("name", ""), "")
        kind, message = outcome(case)
        counts[check][kind] += 1
        if kind == "failed":
            failures[check].append((pair, message.splitlines()[0] if message else ""))
    lines = ["| Check | passed | failed | skipped | xfailed |", "|---|---|---|---|---|"]
    for check, n in sorted(counts.items()):
        lines.append("| `%s` | %d | %d | %d | %d |" % (
            check, n["passed"], n["failed"], n["skipped"], n["xfailed"]))
    for check, items in sorted(failures.items()):
        lines += ["", "**`%s` failures (%d)**" % (check, len(items)), ""]
        lines += ["- `%s`: %s" % (pair, msg) for pair, msg in items[:MAX_LISTED]]
        if len(items) > MAX_LISTED:
            lines.append("- ... and %d more" % (len(items) - MAX_LISTED))
    return lines


def summary_section(path: str) -> List[str]:
    with open(path, encoding="utf-8") as f:
        summary = json.load(f)
    kinds = sorted({k for n in summary.values() for k in n})
    lines = ["| Corpus | %s |" % " | ".join(kinds), "|---|%s" % ("---|" * len(kinds))]
    for corpus, n in sorted(summary.items()):
        lines.append("| %s | %s |" % (corpus, " | ".join(str(n.get(k, 0)) for k in kinds)))
    return lines


def report(paths: List[str], title: str) -> str:
    lines = ["## %s" % title]
    for path in paths:
        lines += ["", "### `%s`" % path, ""]
        lines += summary_section(path) if path.endswith(".json") else junit_section(path)
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Oracle report")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    print(report(args.files, args.title), end="")


if __name__ == "__main__":
    main()
