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

import contextlib
import json
import os
import pathlib
import selectors
import shutil
import signal
import subprocess
import sys
import time

PYTHON = os.path.realpath(os.path.join(sys.base_exec_prefix, "bin", "python3"))
MAX_OUTPUT = 10_000
GRACE = 2.0  # seconds to drain the pipes after the process exits

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
    # earlier sandboxed code can plant a symlink here; the host must not follow it
    if script.is_symlink() or script.exists():
        script.unlink()
    fd = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(code)
    cmd = ["sandbox-exec", "-p", _profile(workdir), PYTHON, "-I", script.name]
    env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
           "HOME": str(workdir), "TMPDIR": str(workdir)}
    # its own process group, so a timeout or exit also ends the children it started
    p = subprocess.Popen(cmd, cwd=workdir, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, start_new_session=True)
    kept = {"stdout": bytearray(), "stderr": bytearray()}
    dropped = {"stdout": 0, "stderr": 0}
    sel = selectors.DefaultSelector()
    for name in kept:
        sel.register(getattr(p, name), selectors.EVENT_READ, name)
    deadline = time.monotonic() + timeout
    out: dict = {}
    stop = None  # once the process is gone: read what is left for GRACE seconds
    while sel.get_map():
        now = time.monotonic()
        if stop is None and (p.poll() is not None or now >= deadline):
            out = ({"exit_code": p.returncode} if p.returncode is not None else
                   {"exit_code": None, "timed_out_after_seconds": timeout})
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(p.pid, signal.SIGKILL)  # its children too
            p.wait()
            # after an exit, let the pipes drain; after a timeout, keep the deadline
            # (never past the run's deadline)
            stop = (min(now + GRACE, max(deadline, now + 0.1))
                    if out["exit_code"] is not None else now + 0.1)
        if stop is not None and now >= stop:
            break  # a descendant in another session still holds a pipe
        for key, _ in sel.select(0.1):
            chunk = os.read(key.fileobj.fileno(), 65536)  # type: ignore[union-attr]
            if not chunk:
                sel.unregister(key.fileobj)
                continue
            name, room = key.data, MAX_OUTPUT - len(kept[key.data])
            kept[name] += chunk[:max(room, 0)]
            dropped[name] += max(len(chunk) - max(room, 0), 0)
    if not out:  # both pipes closed before the process was reaped
        try:
            out = {"exit_code": p.wait(timeout=max(deadline - time.monotonic(), 0))}
        except subprocess.TimeoutExpired:
            out = {"exit_code": None, "timed_out_after_seconds": timeout}
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(p.pid, signal.SIGKILL)
        p.wait()
    sel.close()
    p.stdout.close()  # type: ignore[union-attr]
    p.stderr.close()  # type: ignore[union-attr]
    for k in kept:
        out[k] = kept[k].decode(errors="replace")
        if dropped[k]:
            out[k] += "\n... [truncated %d bytes]" % dropped[k]
    return json.dumps(out)
