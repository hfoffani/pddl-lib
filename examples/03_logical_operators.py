"""Example 03 — Logical operators (#13).

The top-level precondition connective (``and`` vs ``or``) is recovered into the
object model, and negative preconditions are kept separate from positive ones.
Full and/or/not *tree evaluation* is deferred to ADL (#10) — here we just show
what the model exposes.
"""
import os

from pddlpy import DomainProblem

PDDL = os.path.join(os.path.dirname(__file__), "pddl")


def main():
    dp = DomainProblem(
        os.path.join(PDDL, "logic-domain.pddl"),
        os.path.join(PDDL, "logic-problem.pddl"),
    )

    for name in dp.operators():
        op = dp.domain.operators[name]
        print("action %r" % name)
        print("  connective: %s" % op.precondition_connective)
        print("  pre+:", op.precondition_pos)
        print("  pre-:", op.precondition_neg)

    # 'open-door' is disjunctive; 'force-door' is a conjunction with a negation.
    assert dp.domain.operators["open-door"].precondition_connective == "or"
    assert dp.domain.operators["force-door"].precondition_neg


if __name__ == "__main__":
    main()
