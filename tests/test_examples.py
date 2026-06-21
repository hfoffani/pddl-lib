"""Smoke test: every example script under examples/ runs without error.

Keeps the #80 showcase honest — examples are executed as ``__main__`` (so their
in-script assertions run too) and must complete cleanly.
"""
import contextlib
import glob
import io
import os
import runpy

import pytest

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "examples")
SCRIPTS = sorted(glob.glob(os.path.join(EXAMPLES_DIR, "[0-9][0-9]_*.py")))


def test_examples_present():
    assert SCRIPTS, "no example scripts found under examples/"


@pytest.mark.parametrize("script", SCRIPTS, ids=[os.path.basename(s) for s in SCRIPTS])
def test_example_runs(script):
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(script, run_name="__main__")
