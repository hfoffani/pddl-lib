"""#208: obsolete and unmodeled :requirements keys are refused by name."""
import pytest

from pddlpy import DomainProblem
from pddlpy.diagnostics import diagnose
from pddlpy.planning import PlannerError, get
from pddlpy.planning.base import OBSOLETE_REQUIREMENTS, UNMODELED_REQUIREMENTS
from pddlpy.planning.validation import validate_plan


@pytest.mark.parametrize("key", sorted(OBSOLETE_REQUIREMENTS | UNMODELED_REQUIREMENTS))
@pytest.mark.parametrize("in_problem", [False, True])
@pytest.mark.parametrize("upper", [False, True])
def test_key_is_refused_by_name(tmp_path, key, in_problem, upper):
    """Review on #209: a problem file may declare requirements too."""
    d, p = tmp_path / "d.pddl", tmp_path / "p.pddl"
    written = key.upper() if upper else key
    d.write_text("(define (domain d) (:requirements :strips %s) (:predicates (p))"
                 " (:action a :parameters () :effect (p)))" % ("" if in_problem else written))
    p.write_text("(define (problem p) (:domain d) %s (:init) (:goal (p)))"
                 % ("(:requirements %s)" % written if in_problem else ""))
    dp = DomainProblem(str(d), str(p))
    assert not dp.syntax_errors and key in dp.requirements()
    reason = "obsolete PDDL 1.2" if key in OBSOLETE_REQUIREMENTS else "not supported yet"
    with pytest.raises(PlannerError, match="%s: %s" % (key, reason)):
        get("bfs").solve(dp)
    with pytest.raises(PlannerError, match=key):
        validate_plan(dp, [])
    issues = diagnose(str(d), str(p))["issues"]
    assert [i["check"] for i in issues if i["severity"] == "error"] == ["unsupported"]
