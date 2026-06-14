"""Phase 0 triage regression markers.

- #16 (`No module named '__builtin__'`): Python 2 leftover. Confirmed gone
  on 3.11+; guarded so it cannot creep back in.
- #27 / #23: user-supplied durative-action files fail to parse. Confirmed a
  duplicate of #23 (durative-action recovery is incomplete); xfail until
  Phase 4 implements it.
"""
import os

import pytest

from pddlpy import DomainProblem

CORPUS = os.path.join(os.path.dirname(__file__), "corpus")


def test_no_python2_builtin_import():
    """#16: importing the library must not pull in the py2-only
    `__builtin__` module."""
    import importlib
    import pddlpy.pddl as pddl

    importlib.reload(pddl)  # exercises the module's imports
    assert "__builtin__" not in dir(pddl)


@pytest.mark.xfail(
    reason="#27/#23: durative-action recovery incomplete; no enterDurativeActionDef "
    "scope is pushed, so enterTypedVariableList raises IndexError. Deferred to Phase 4.",
    raises=IndexError,
    strict=True,
)
def test_durative_action_parses():
    dp = DomainProblem(
        os.path.join(CORPUS, "durative-action-domain.pddl"),
        os.path.join(CORPUS, "durative-action-problem.pddl"),
    )
    assert "go" in set(dp.operators())
    assert len(dp.goals()) > 0
