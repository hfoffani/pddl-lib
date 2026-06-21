"""Example 01 — Parsing basics.

Parse a typed STRIPS domain/problem (gripper) and read the core object model:
objects, operators, initial state, goals, and the grounded instances of an
operator. Start here.
"""
import os

from pddlpy import DomainProblem

PDDL = os.path.join(os.path.dirname(__file__), "pddl")


def main():
    dp = DomainProblem(
        os.path.join(PDDL, "gripper-domain.pddl"),
        os.path.join(PDDL, "gripper-problem.pddl"),
    )

    print("operators:", list(dp.operators()))
    print("objects:  ", dp.worldobjects())
    print("init:     ", dp.initialstate())
    print("goals:    ", dp.goals())

    print("\ngrounded 'pick' instances:")
    for op in dp.ground_operator("pick"):
        print("  vars:", op.variable_list)
        print("    pre+:", op.precondition_pos, " pre-:", op.precondition_neg)
        print("    eff+:", op.effect_pos, " eff-:", op.effect_neg)


if __name__ == "__main__":
    main()
