"""Exact failure reports for malformed plans (mutation testing): an agent
acts on ``message`` and the other ``Failure`` fields, so they are pinned."""
import pytest

from pddlpy import DomainProblem
from pddlpy.planning import PlanStep, State, plan_from_json, validate_plan
from pddlpy.planning.validation import TOLERANCE, PlanValidationError

DOMAIN = """(define (domain v)
 (:requirements :strips :typing :durative-actions :duration-inequalities)
 (:types ball room)
 (:predicates (at ?b - ball ?r - room) (p))
 (:action move :parameters (?b - ball ?r - room) :precondition (and) :effect (at ?b ?r))
 (:durative-action fixed :parameters () :duration (= ?duration 2)
   :condition (and) :effect (at end (p)))
 (:durative-action ranged :parameters ()
   :duration (and (>= ?duration 1) (<= ?duration 3))
   :condition (and) :effect (at end (p))))"""
PROBLEM = """(define (problem v1) (:domain v)
 (:objects b1 - ball r1 - room) (:init) (:goal (p)))"""


@pytest.fixture
def dp(tmp_path):
    (tmp_path / "d.pddl").write_text(DOMAIN)
    (tmp_path / "p.pddl").write_text(PROBLEM)
    return DomainProblem(str(tmp_path / "d.pddl"), str(tmp_path / "p.pddl"))


@pytest.mark.parametrize("step,kind,message", [
    (PlanStep("fly", (), 0.5), "unknown-action",
     "step 1 (fly): the domain has no action 'fly'"),
    (PlanStep("move", ("b1",), 0.5), "arity",
     "step 1 (move b1): move takes 2 arguments, got 1"),
    (PlanStep("move", ("b1", "x"), 0.5), "unknown-object",
     "step 1 (move b1 x): the problem has no object 'x'"),
    (PlanStep("move", ("r1", "b1"), 0.5), "type",
     "step 1 (move r1 b1): r1 is not of type ball (parameter ?b)"),
    (PlanStep("fixed", (), 0.5), "duration",
     "step 1 (fixed): durative action fixed needs a [duration] (2)"),
    (PlanStep("ranged", (), 0.5), "duration",
     "step 1 (ranged): durative action ranged needs a [duration] (from 1 to 3)"),
    (PlanStep("ranged", (), 0.5, 5.0), "duration",
     "step 1 (ranged): duration 5, but ranged takes from 1 to 3"),
    (PlanStep("ranged", (), 0.5, 3 + TOLERANCE), "duration",
     "step 1 (ranged): duration 3.01, but ranged takes from 1 to 3"),
    (PlanStep("fixed", (), 0.5, 3.0), "duration",
     "step 1 (fixed): duration 3, but fixed takes 2"),
])
def test_malformed_step_failure(dp, step, kind, message):
    failure = validate_plan(dp, [step]).failure
    assert failure == (kind, message, 1, str(step), 0.5, (), State.from_problem(dp))


def test_binding_names_the_parameters(dp):
    steps = plan_from_json([{"action": "move", "args": {"?b": "b1", "?x": "r1"}}])
    assert validate_plan(dp, steps).failure.message == \
        "step 1 (move b1 r1): move takes parameters ?b ?r"


def test_non_finite_time_message(dp):
    with pytest.raises(PlanValidationError,
                       match=r"^step 1 \(move b1 r1\): time and duration must be finite numbers$"):
        validate_plan(dp, [PlanStep("move", ("b1", "r1"), float("nan"))])
