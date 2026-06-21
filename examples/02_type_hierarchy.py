"""Example 02 — Type hierarchies (#22).

The logistics domain declares a multi-level `:types` hierarchy
(``truck - vehicle``, ``vehicle - physobj``, ``airport - location`` ...). A
parameter typed with a supertype binds objects of any transitive subtype, so
grounding respects the hierarchy. Inspect it with ``types()`` /
``subtypes_of()``.
"""
import os

from pddlpy import DomainProblem

PDDL = os.path.join(os.path.dirname(__file__), "pddl")


def main():
    dp = DomainProblem(
        os.path.join(PDDL, "logistics-domain.pddl"),
        os.path.join(PDDL, "logistics-problem.pddl"),
    )

    print("types (subtype -> direct supertype):")
    for sub, sup in sorted(dp.types().items()):
        print("  %-10s -> %s" % (sub, sup))

    print("\nall transitive subtypes of 'object':", sorted(dp.subtypes_of("object")))
    print("all transitive subtypes of 'vehicle':", sorted(dp.subtypes_of("vehicle")))

    # 'load-truck' takes a ?loc typed 'location'; airports (a subtype) bind too.
    n = sum(1 for _ in dp.ground_operator("load-truck"))
    print("\ngrounded 'load-truck' instances (supertype binding in action):", n)


if __name__ == "__main__":
    main()
