"""JSON-friendly views of the object model (#85).

Plain-dict renderings of ``DomainProblem``, grounded ``Operator``,
``Plan`` and plan validation results (#166), shared by the command-line interface (#85) and the MCP server
(#86). Everything returned is composed of JSON-serializable types only:
atoms become sorted lists of token lists, sets become sorted lists, and
numeric expressions are rendered through their ``repr``.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Union

from pddlpy.pddl import DomainProblem, Operator
from pddlpy.planning import (
    Failure,
    Plan,
    Simulation,
    State,
    TemporalPlan,
    Validation,
    atom_tuple,
)


def number(value: float) -> Union[float, str]:
    """A number for JSON: finite values as they are, an infinity or NaN
    (IEEE division by zero) as ``"inf"`` / ``"-inf"`` / ``"nan"``, which
    strict JSON has no literal for."""
    if math.isfinite(value):
        return value
    return "nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")


def atoms_list(atoms: Iterable[Any]) -> List[List[str]]:
    """Render a collection of atoms/tuples as a sorted list of token lists."""
    return sorted(list(atom_tuple(a)) for a in atoms)


def domain_problem_dict(dp: DomainProblem) -> Dict[str, Any]:
    """Summary of a parsed domain/problem pair."""
    metric = dp.metric()
    return {
        "requirements": sorted(dp.requirements()),
        "objects": dict(sorted(dp.worldobjects().items())),
        "types": dict(sorted(dp.types().items())),
        "predicates": sorted(dp.predicates()),
        "operators": sorted(dp.operators()),
        "durative_operators": sorted(dp.durative_operators()),
        "initial_state": atoms_list(dp.initialstate()),
        "goals": atoms_list(dp.goals()),
        "initial_numeric": {
            " ".join(head): value
            for head, value in sorted(dp.initial_numeric().items())
        },
        "metric": (
            {"optimization": metric[0], "expression": metric[1]}
            if metric is not None
            else None
        ),
    }


def operator_dict(op: Operator) -> Dict[str, Any]:
    """A grounded instantaneous action."""
    return {
        "name": op.operator_name,
        "parameters": dict(op.variable_list),
        "precondition_connective": op.precondition_connective,
        "precondition_pos": atoms_list(op.precondition_pos),
        "precondition_neg": atoms_list(op.precondition_neg),
        "effect_pos": atoms_list(op.effect_pos),
        "effect_neg": atoms_list(op.effect_neg),
        "precondition_num": [repr(c) for c in op.precondition_num],
        "effect_num": [repr(e) for e in op.effect_num],
    }


def plan_dict(plan: Optional[Plan]) -> Dict[str, Any]:
    """A plan (or the absence of one, when ``plan`` is ``None``).

    A :class:`TemporalPlan` (#84) additionally carries its schedule (#119):
    each step gains ``start``, ``duration`` and ``end``, and the dict gains a
    top-level ``makespan`` (which also remains the ``cost``).
    """
    if plan is None:
        return {"solved": False, "cost": None, "length": None, "steps": None}
    if isinstance(plan, TemporalPlan):
        return {
            "solved": True,
            "cost": number(plan.cost),
            "makespan": number(plan.makespan),
            "length": len(plan),
            "steps": [
                {
                    "action": s.action.operator_name,
                    "args": dict(s.action.variable_list),
                    "start": s.start,
                    "duration": s.duration,
                    "end": s.end,
                }
                for s in plan.steps
            ],
        }
    return {
        "solved": True,
        "cost": number(plan.cost),
        "length": len(plan),
        "steps": [
            {"action": name, "args": dict(bindings)}
            for name, bindings in plan.action_names()
        ],
    }


def state_dict(state: State) -> Dict[str, Any]:
    """A state: its atoms, and its numeric fluents keyed like
    ``initial_numeric``."""
    return {
        "atoms": atoms_list(state.atoms),
        "fluents": {" ".join(head): number(v) for head, v in sorted(state.fluents.items())},
    }


def failure_dict(failure: Optional[Failure]) -> Optional[Dict[str, Any]]:
    """Why a plan fails: ``kind``, ``message``, the 1-based ``step`` and its
    ``action`` and ``time`` (null for an unmet goal), the ``unmet``
    conditions or goal atoms, and the ``state`` they were checked in."""
    if failure is None:
        return None
    return {
        "kind": failure.kind,
        "message": failure.message,
        "step": failure.step,
        "action": failure.action,
        "time": failure.time,
        "unmet": list(failure.unmet),
        "state": state_dict(failure.state),
    }


def validation_dict(result: Validation) -> Dict[str, Any]:
    """A ``validate_plan`` verdict."""
    return {"valid": result.valid, "failure": failure_dict(result.failure)}


def simulation_dict(sim: Simulation) -> Dict[str, Any]:
    """A ``simulate`` run: the state after each happening part, up to the
    first failure."""
    return {
        "executed": sim.executed,
        "failure": failure_dict(sim.failure),
        "trace": [
            {"time": p.time, "event": p.event, "step": p.step, "action": p.action,
             "state": state_dict(p.state)}
            for p in sim.trace
        ],
        "final_state": state_dict(sim.state),
    }
