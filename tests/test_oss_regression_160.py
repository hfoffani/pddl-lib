"""Domain constants keep their declared types when objects are inferred."""

import pytest

from pddlpy import DomainProblem


@pytest.mark.parametrize("objects_section", ["", "(:objects)"])
def test_inferred_objects_preserve_constant_types_and_grounding(tmp_path, objects_section):
    names = [f"plane_{i}" for i in range(64)]
    domain_objects = dict.fromkeys([*names, "unused"], "airplane")
    domain = tmp_path / "domain.pddl"
    problem = tmp_path / "problem.pddl"
    domain.write_text(
        "(define (domain airport) (:requirements :strips :typing)"
        " (:types airplane)"
        f" (:constants {' '.join(domain_objects)} - airplane)"
        " (:predicates (ready ?p - airplane) (done ?p - airplane) (marker ?x))"
        " (:action move :parameters (?p - airplane)"
        " :precondition (ready ?p) :effect (done ?p)))"
    )
    problem.write_text(
        "(define (problem flight) (:domain airport)"
        f" {objects_section}"
        f" (:init {' '.join(f'(ready {name})' for name in names)} (marker init_only))"
        " (:goal (and (done plane_0) (marker goal_only))))"
    )
    dp = DomainProblem(str(domain), str(problem))
    inferred = dict(dp.problem.objects)
    assert all(inferred[name] is None for name in names)

    objects = dp.worldobjects()
    assert {name: objects[name] for name in domain_objects} == domain_objects, (
        "declared constants lost their types when merged with inferred objects"
    )
    assert objects["init_only"] is None
    assert objects["goal_only"] is None
    assert set(dp.candidate_objects("airplane")) == set(domain_objects)
    assert {op.variable_list["?p"] for op in dp.ground_operator("move")} == set(names)
    assert dp.domain.objects == domain_objects
    assert dp.problem.objects == inferred
