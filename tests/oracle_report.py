"""Markdown report of an oracle run (#153), for the oracle workflow.

    python tests/oracle_report.py [--title T] FILE...

Each FILE is a pytest JUnit XML (``make oracle PYTEST_ARGS=--junitxml=...``)
or a ``summary.json`` from ``make corpora-test``. The report counts outcomes
per oracle check and lists each failing pair with the first line of its
message, marked with its known cause (``KNOWN_CAUSES``) or as **NEW**.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

MAX_LISTED = 50  # failures listed per check; the rest are counted

# Known causes of disagreements on the corpora, so the report-only corpus
# jobs set new ones apart: (check regex, pair regex, cause). Each entry was
# checked against the failing files (oracle runs on #156). Remove an entry
# once its cause is fixed; a failure matching no entry is reported as NEW.
KNOWN_CAUSES: List[Tuple[str, str, str]] = [
    (r"fd_plan|solvability",
     r"classical/blocks/|blocks-strips-|classical/schedule/|schedule-adl-|freecell-strips-"
     r"|ged-opt14-strips|genome-edit-distances|depots-strips-|/rovers|rovers-"
     r"|logistics-round-2-strips",
     "#157 identifier case (predicates, types, static facts)"),
    (r"accept|fd_plan",
     r"derived-predicates|classical/(psr-large|psr-middle|philosophers|optical-telegraphs)/",
     "#141 (:derived ...) does not parse"),
    (r"fd_plan|solvability|pddlpy_plan",
     r"elevator-adl-full|elevators-00-full|miconic-fulladl|petri-net-alignment|snake-opt18"
     r"|psr-middle-compiled-adl|tpp-metric",
     "#138 goal other than a positive conjunction (forall, not, numeric)"),
    (r"fd_plan|solvability", r"airport",
     "#160 domain constants lose their type"),
    (r"accept", r"classical/fridge/|classical/tyreworld/|pathways-propositional",
     "FD rejects the input, pddlpy accepts it (not yet diagnosed)"),
]


def known_cause(check: str, pair: str) -> Optional[str]:
    """The known cause of a failing (check, pair), or ``None`` if new."""
    for check_re, pair_re, cause in KNOWN_CAUSES:
        if re.search(check_re, check) and re.search(pair_re, pair):
            return cause
    return None


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
    failures: Dict[str, List[Tuple[Optional[str], str, str]]] = collections.defaultdict(list)
    for case in ET.parse(path).getroot().iter("testcase"):
        m = re.match(r"([^\[]+)(?:\[(.*)\])?$", case.get("name", ""))
        check, pair = (m.group(1), m.group(2) or "") if m else (case.get("name", ""), "")
        kind, message = outcome(case)
        counts[check][kind] += 1
        if kind == "failed":
            cause = known_cause(check, pair)
            counts[check]["new"] += cause is None
            failures[check].append((cause, pair, message.splitlines()[0] if message else ""))
    new = sum(n["new"] for n in counts.values())
    failed = sum(n["failed"] for n in counts.values())
    lines = ["**%d failures: %d new, %d with a known cause.**" % (failed, new, failed - new), "",
             "| Check | passed | failed | new | skipped | xfailed |", "|---|---|---|---|---|---|"]
    for check, n in sorted(counts.items()):
        lines.append("| `%s` | %d | %d | %d | %d | %d |" % (
            check, n["passed"], n["failed"], n["new"], n["skipped"], n["xfailed"]))
    for check, items in sorted(failures.items()):
        items.sort(key=lambda item: (item[0] is not None, item[1]))  # new first
        lines += ["", "**`%s` failures (%d)**" % (check, len(items)), ""]
        lines += ["- %s `%s`: %s" % ("**NEW**" if cause is None else "known: %s —" % cause,
                                     pair, msg)
                  for cause, pair, msg in items[:MAX_LISTED]]
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
