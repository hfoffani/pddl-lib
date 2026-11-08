"""``run_python`` tool for the python arm: run model-written code, contained.

- the base interpreter (no venv, so no pddlpy or other third-party packages),
  ``-I`` isolated mode, a stripped environment;
- cwd is a fresh temp dir per run; macOS ``sandbox-exec`` denies network
  access, writes outside that dir, and reads under /Users other than that dir
  and the interpreter (stdout goes back to the model's API, so a read is a leak);
- a wall-clock timeout kills runaway searches.

Fails closed: without ``sandbox-exec`` (i.e. off macOS) the tool refuses to
run. A guard rail for a manual playground, not a hardened jail.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys

PYTHON = os.path.realpath(os.path.join(sys.base_exec_prefix, "bin", "python3"))
MAX_OUTPUT = 10_000

TOOL = {
    "type": "function",
    "function": {
        "name": "run_python",
        "description": "Run a Python 3 program (standard library only, no network) "
                       "and return its stdout, stderr and exit code. Files written "
                       "to the current directory persist between calls.",
        "parameters": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "the program"}},
            "required": ["code"],
        },
    },
}


def _profile(workdir: pathlib.Path) -> str:
    real = os.path.realpath(workdir)
    prefixes = {os.path.realpath(sys.base_exec_prefix), sys.base_exec_prefix,
                os.path.dirname(os.path.dirname(PYTHON))}
    return ('(version 1)(allow default)(deny network*)'
            '(deny file-write*)(allow file-write* (subpath "%s") (literal "/dev/null"))'
            '(deny file-read* (subpath "/Users"))'
            '(allow file-read* (subpath "%s") %s)' % (
                real, real, " ".join('(subpath "%s")' % p for p in sorted(prefixes))))


def run_python(code: str, workdir: pathlib.Path, timeout: float = 60.0,
               n: int = 0) -> str:
    """Run ``code`` in ``workdir``; JSON result text for the model."""
    if not shutil.which("sandbox-exec"):
        return json.dumps({"error": "run_python is unavailable: no sandbox "
                                    "(sandbox-exec) on this machine"})
    script = workdir / ("run_%d.py" % n)
    script.write_text(code, encoding="utf-8")
    cmd = ["sandbox-exec", "-p", _profile(workdir), PYTHON, "-I", script.name]
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(workdir), "TMPDIR": str(workdir)}
    try:
        p = subprocess.run(cmd, cwd=workdir, env=env, capture_output=True,
                           text=True, timeout=timeout)
        out = {"exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except subprocess.TimeoutExpired as exc:
        def text(b):
            return b.decode(errors="replace") if isinstance(b, bytes) else (b or "")
        out = {"exit_code": None, "timed_out_after_seconds": timeout,
               "stdout": text(exc.stdout), "stderr": text(exc.stderr)}
    for k in ("stdout", "stderr"):
        if len(out[k]) > MAX_OUTPUT:
            out[k] = out[k][:MAX_OUTPUT] + "\n... [truncated %d chars]" % (
                len(out[k]) - MAX_OUTPUT)
    return json.dumps(out)
