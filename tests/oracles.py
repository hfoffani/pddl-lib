"""Thin wrappers for the external oracles (#153), plus plan I/O and replay.

Fast Downward (translator + search), VAL and INVAL run as subprocesses
only. Each ``*_bin()`` returns ``None`` when the tool is missing, so tests
can skip cleanly. Lookup order: an explicit environment variable
(``FAST_DOWNWARD``, ``VALIDATE``, ``INVAL``), then ``ORACLES_DIR`` (default
``.oracles``, filled by ``make oracles``), then ``PATH``.

A plan is a list of steps ``(action, (arg, ...))``. Fast Downward writes
names in lower case, so lookups against pddlpy's grounding are
case-insensitive.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

from pddlpy import DomainProblem
from pddlpy.planning import GroundedTask, State

Step = Tuple[str, Tuple[str, ...]]

# Fast Downward exit codes (driver/returncodes.py).
FD_SUCCESS = 0
FD_TRANSLATE_UNSOLVABLE = 10
FD_SEARCH_UNSOLVABLE = 11
FD_TRANSLATE_CRITICAL_ERROR = 30
FD_TRANSLATE_INPUT_ERROR = 31
# The translator's verdicts on its input. Any other exit (a resource limit,
# a driver error, a kill signal such as 247 = -9) says nothing about it.
FD_ACCEPTS = {FD_SUCCESS, FD_TRANSLATE_UNSOLVABLE}
FD_REJECTS = {FD_TRANSLATE_CRITICAL_ERROR, FD_TRANSLATE_INPUT_ERROR}
# Out of memory/time in the translator or search: no verdict on the input.
FD_RESOURCE_LIMIT = {20, 21, 22, 23, 24}

# REQUIREMENT_LABELS of FD's translator (translate/pddl/tasks.py); it
# refuses any other key, so such domains stay outside the FD comparison.
FD_REQUIREMENTS = {
    ":strips", ":typing", ":negation", ":negative-preconditions",
    ":disjunctive-preconditions",
    ":equality", ":existential-preconditions", ":universal-preconditions",
    ":quantified-preconditions", ":conditional-effects", ":adl",
    ":derived-predicates", ":action-costs",
}


def _oracles_dir() -> str:
    return os.environ.get("ORACLES_DIR") or ".oracles"


def _find(env: str, built: str, *names: str) -> Optional[str]:
    """An absolute path: the tools run with a temporary ``cwd``, where a
    relative path would no longer resolve."""
    explicit = os.environ.get(env)
    if explicit:
        if os.sep in explicit:
            return os.path.abspath(explicit)
        return shutil.which(explicit) or explicit
    path = os.path.join(_oracles_dir(), built)
    if os.path.exists(path):
        return os.path.abspath(path)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def fast_downward_bin() -> Optional[str]:
    return _find("FAST_DOWNWARD", "downward/fast-downward.py",
                 "fast-downward.py", "fast-downward")


def validate_bin() -> Optional[str]:
    return _find("VALIDATE", "VAL/build/bin/Validate", "Validate", "validate")


def inval_bin() -> Optional[str]:
    return _find("INVAL", "INVAL/inval", "inval")


def _command(binary: str) -> List[str]:
    return [sys.executable, binary] if binary.endswith(".py") else [binary]


def _run(cmd: Sequence[str], timeout: float, cwd: Optional[str] = None
         ) -> Optional[subprocess.CompletedProcess]:
    """Run ``cmd``; ``None`` on timeout."""
    try:
        return subprocess.run(list(cmd), cwd=cwd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return None


def declared_requirements(domain: str) -> List[str]:
    """The ``:requirements`` keys of a domain file, read textually."""
    with open(domain, encoding="utf-8", errors="replace") as f:
        m = re.search(r"\(:requirements([^)]*)\)", f.read().lower())
    return m.group(1).split() if m else []


def fd_supports(domain: str) -> bool:
    return set(declared_requirements(domain)) <= FD_REQUIREMENTS


# Blind A* can fill a CI runner's memory within seconds; past this cap FD
# exits 20/22 (out of memory), which the checks treat as no verdict.
FD_MEMORY = "2G"
# Extra seconds before the subprocess timeout, so FD's own time limit fires
# first and reports through its exit code.
FD_GRACE = 10


def _fd_limits(timeout: float) -> List[str]:
    return ["--overall-time-limit", "%ds" % max(1, int(timeout)),
            "--overall-memory-limit", FD_MEMORY]


def fd_translate(fd: str, domain: str, problem: str, timeout: float) -> Optional[int]:
    """Exit code of FD's translator on the pair; ``None`` when it ran out of
    time or memory, which says nothing about whether it accepts the input."""
    with tempfile.TemporaryDirectory() as tmp:
        proc = _run(_command(fd) + _fd_limits(timeout) + [
            "--translate", os.path.abspath(domain), os.path.abspath(problem),
        ], timeout + FD_GRACE, cwd=tmp)
    if proc is None or proc.returncode in FD_RESOURCE_LIMIT:
        return None
    return proc.returncode


def fd_solve(fd: str, domain: str, problem: str, timeout: float
             ) -> Tuple[Optional[int], Optional[List[Step]]]:
    """Run FD with a complete search (A* with the blind heuristic), so exit
    code 11 proves unsolvability. Returns ``(exit code, plan)``; the code is
    ``None`` on timeout and the plan ``None`` when none was written."""
    with tempfile.TemporaryDirectory() as tmp:
        plan_file = os.path.join(tmp, "plan")
        proc = _run(_command(fd) + _fd_limits(timeout) + [
            "--plan-file", plan_file,
            os.path.abspath(domain), os.path.abspath(problem),
            "--search", "astar(blind())",
        ], timeout + FD_GRACE, cwd=tmp)
        plan = read_plan(plan_file) if os.path.exists(plan_file) else None
    return (None if proc is None else proc.returncode), plan


def val(validate: str, domain: str, problem: str, plan_file: str,
        timeout: float) -> Optional[bool]:
    """VAL's verdict: its exit code counts errors, and a valid plan prints
    'Plan valid'. ``None`` on timeout."""
    proc = _run([validate, domain, problem, plan_file], timeout)
    if proc is None:
        return None
    return proc.returncode == 0 and "Plan valid" in proc.stdout


def val_log(validate: str, domain: str, problem: str, plan_file: str,
            timeout: float, lines: int = 8) -> str:
    """The last lines of VAL's verbose output on the plan (``-v``), for a
    failure message that says why VAL rejected it."""
    proc = _run([validate, "-v", domain, problem, plan_file], timeout)
    if proc is None:
        return "VAL timed out"
    text = (proc.stdout + proc.stderr).strip().splitlines()
    return "VAL exit %d: %s" % (proc.returncode, " | ".join(text[-lines:]))


def inval(binary: str, domain: str, problem: str, plan_file: str,
          timeout: float) -> Optional[bool]:
    """INVAL's verdict, from its 'plan NAME: valid|not valid, ...' line."""
    proc = _run([binary, domain, problem, plan_file], timeout)
    if proc is None:
        return None
    m = re.search(r"^plan .*: (valid|not valid),", proc.stdout, re.MULTILINE)
    return bool(m) and m.group(1) == "valid"


_STEP = re.compile(r"^\s*(?:[\d.]+\s*:\s*)?\(([^)]*)\)")


def read_plan(path: str) -> List[Step]:
    """Read a plan file: one '(action arg ...)' per line, optionally with a
    'time:' prefix and a '[duration]' suffix; ';' lines are comments."""
    steps = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _STEP.match(line)
            if m and not line.lstrip().startswith(";"):
                name, *args = m.group(1).split()
                steps.append((name, tuple(args)))
    return steps


def write_plan(steps: Sequence[Step], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for name, args in steps:
            f.write("(%s)\n" % " ".join((name,) + tuple(args)))


def _args(dp: DomainProblem, op) -> Tuple[str, ...]:
    """A grounded action's arguments in the operator's declared parameter
    order. The grounded bindings come in binder order, so take the order
    from the lifted operator."""
    name = op.operator_name
    table = dp.domain.operators if name in dp.domain.operators else dp.domain.durative_operators
    lifted = table[name].variable_list
    return tuple(str(op.variable_list[v]) for v in lifted)


def plan_steps(dp: DomainProblem, plan) -> List[Step]:
    """The steps of a pddlpy ``Plan``."""
    return [(a.operator_name, _args(dp, a)) for a in plan]


def replay(dp: DomainProblem, steps: Sequence[Step]) -> Optional[str]:
    """Execute ``steps`` with pddlpy's grounding and apply semantics.
    Returns ``None`` if the plan reaches the goal, else why it fails."""
    task = GroundedTask(dp)
    index: Dict[Step, object] = {}
    for op in task.actions:
        key = (op.operator_name.lower(), tuple(a.lower() for a in _args(dp, op)))
        index[key] = op
    state: State = task.initial
    for i, (name, args) in enumerate(steps, 1):
        op = index.get((name.lower(), tuple(a.lower() for a in args)))
        if op is None:
            return "step %d (%s %s): not a grounded action" % (i, name, " ".join(args))
        if not state.applicable(op):
            return "step %d (%s %s): not applicable" % (i, name, " ".join(args))
        state = state.apply(op)
    if not task.is_goal(state):
        return "goal not satisfied after %d steps" % len(steps)
    return None
