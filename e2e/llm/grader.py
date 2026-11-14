"""Grade an English answer against a scenario's reference PDDL.

answer --(regex pre-pass, else extractor LLM)--> plan steps of the reference
domain --validate_plan--> verdict:

    optimal           valid plan at the optimum cost
    suboptimal        valid plan, cost above the optimum
    goal-not-reached  every step runs, the goal does not hold at the end
    invalid           a step is malformed or cannot run
    unparseable       no plan could be read from the answer
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from scenarios import Scenario, final_cost

from pddlpy.planning import PlanStep, PlanValidationError, parse_plan, validate_plan

#: prompt -> completion text (an LLM call at temperature 0)
Extractor = Callable[[str], str]

OPTIMAL, SUBOPTIMAL, GOAL, INVALID, UNPARSEABLE = (
    "optimal", "suboptimal", "goal-not-reached", "invalid", "unparseable")

_STEP = re.compile(r"\(\s*([A-Za-z][\w-]*)((?:\s+[\w-]+)*)\s*\)")


@dataclass
class Grade:
    verdict: str
    cost: Optional[float] = None
    optimum: Optional[float] = None
    steps: List[str] = field(default_factory=list)
    detail: str = ""
    source: str = ""          # "regex" | "extractor" | ""

    @property
    def passed(self) -> bool:
        return self.verdict == OPTIMAL


def regex_steps(answer: str, actions: set) -> List[PlanStep]:
    """``(action arg ...)`` groups naming a domain action, in order."""
    out = []
    for m in _STEP.finditer(answer):
        name = m.group(1).lower()
        if name in actions:
            out.append(PlanStep(name, tuple(a.lower() for a in m.group(2).split())))
    return out


def extractor_prompt(sc: Scenario, answer: str) -> str:
    dp = sc.reference()
    sigs = "\n".join("(%s %s)" % (name, " ".join(
        "%s - %s" % (v, t) for v, t in op.variable_list.items()))
        for name, op in sorted(dp.domain.operators.items()))
    objs = ", ".join("%s (%s)" % (o, t) for o, t in sorted(dp.worldobjects().items()))
    return (
        "Below is a problem statement and someone's answer to it. Rewrite the plan "
        "the ANSWER proposes as a sequence of formal actions.\n\n"
        "Actions (name and typed parameters):\n%s\n\nObjects: %s\n\n"
        "Rules:\n- Output ONLY the plan: one `(action arg1 arg2 ...)` per line, "
        "arguments in the parameter order above, exact names from the lists.\n"
        "- Transcribe what the answer says, step by step, even if it is wrong. "
        "Do not fix, complete, or re-solve it. If the answer skips intermediate "
        "steps that are implied unambiguously (e.g. a route listed as places), "
        "spell them out.\n"
        "- If the answer contains no plan, or it cannot be mapped to these "
        "actions, output exactly NONE.\n\n"
        "PROBLEM:\n%s\n\nANSWER:\n%s\n" % (sigs, objs, sc.text, answer))


def extract(sc: Scenario, answer: str, extractor: Optional[Extractor]):
    actions = set(sc.reference().domain.operators)
    steps = regex_steps(answer, actions)
    if steps:
        return steps, "regex"
    if extractor is None:
        return None, ""
    text = extractor(extractor_prompt(sc, answer)).strip()
    text = re.sub(r"^```\w*\s*|\s*```$", "", text)
    if not text or text.upper().startswith("NONE"):
        return None, "extractor"
    try:
        return [PlanStep(s.name.lower(), tuple(a.lower() for a in s.args))
                for s in parse_plan(text)], "extractor"
    except PlanValidationError:
        steps = regex_steps(text, actions)
        return (steps or None), "extractor"


def grade(sc: Scenario, answer: str, extractor: Optional[Extractor] = None) -> Grade:
    steps, source = extract(sc, answer, extractor)
    if not steps:
        return Grade(UNPARSEABLE, optimum=sc.optimal_cost, source=source,
                     detail="no plan found in the answer")
    shown = [str(s) for s in steps]
    try:
        v = validate_plan(sc.reference(), steps)
    except PlanValidationError as exc:
        return Grade(INVALID, None, sc.optimal_cost, shown, str(exc), source)
    if not v.valid:
        kind = GOAL if v.failure.kind == "goal" else INVALID  # type: ignore[union-attr]
        return Grade(kind, None, sc.optimal_cost, shown,
                     v.failure.message, source)  # type: ignore[union-attr]
    cost = final_cost(v.simulation.state, len(steps))
    verdict = OPTIMAL if cost <= sc.optimal_cost + 1e-9 else SUBOPTIMAL
    return Grade(verdict, cost, sc.optimal_cost, shown, "", source)
