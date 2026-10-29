"""Plan validation probes (roadmap step 3), shared by tests/test_validation.py
(pddlpy's verdicts) and tests/test_oracle.py (VAL gives the same ones).

Each case is ``(id, pair, plan text, valid, failure kind)``; the pairs are
under tests/corpus/validation/.
"""
import os

HERE = os.path.join(os.path.dirname(__file__), "corpus", "validation")
TEMPORAL = (os.path.join(HERE, "temporal-domain.pddl"), os.path.join(HERE, "temporal-problem.pddl"))
ADL = (os.path.join(HERE, "adl-domain.pddl"), os.path.join(HERE, "adl-problem.pddl"))

CASES = [
    # temporal: happenings, separation, durations, invariants
    ("separated", TEMPORAL, "0: (a) [2]\n2.01: (b) [3]\n", True, None),
    ("out-of-order", TEMPORAL, "2.01: (b) [3]\n0: (a) [2]\n", True, None),
    ("same-time", TEMPORAL, "0: (a) [2]\n2: (b) [3]\n", False, "precondition"),
    ("within-epsilon", TEMPORAL, "0: (a) [2]\n2.001: (b) [3]\n", False, "precondition"),
    ("past-epsilon", TEMPORAL, "0: (a) [2]\n2.0011: (b) [3]\n", True, None),
    ("duration-close", TEMPORAL, "0: (a) [2.0099]\n3: (b) [3]\n", True, None),
    ("duration-off", TEMPORAL, "0: (a) [2.02]\n3: (b) [3]\n", False, "duration"),
    ("duration-short", TEMPORAL, "0: (a) [1.99]\n3: (b) [3]\n", False, "duration"),
    ("no-duration", TEMPORAL, "0: (a)\n3: (b) [3]\n", False, "duration"),
    ("untimed", TEMPORAL, "(a)\n(b)\n", False, "duration"),
    ("invariant", TEMPORAL, "0: (a) [2]\n2.5: (b) [3]\n3: (k) [1]\n", False, "invariant"),
    ("invariant-at-end", TEMPORAL, "0: (a) [2]\n2.5: (b) [3]\n4.5: (k) [1]\n", True, None),
    ("end-condition", TEMPORAL, "0: (a) [2]\n2.5: (b) [3]\n3: (c) [1]\n", False,
     "end-condition"),
    ("mutex-add-delete", TEMPORAL, "0: (a) [2]\n1: (k) [1]\n", False, "mutex"),
    ("instant-in-temporal", TEMPORAL, "0: (a) [2]\n2.5: (b) [3]\n6: (tick)\n", True, None),
    # instantaneous: steps, objects, types, numeric, ADL
    ("undefined-fluent", ADL, "(low a)\n", False, "undefined-fluent"),
    ("undefined-in-unmet", ADL, "(rd a)\n", False, "precondition"),
    ("numeric-precondition", ADL, "(asg a)\n(rd a)\n", False, "precondition"),
    ("increase-undefined", ADL, "(inc a)\n", True, None),
    ("wrong-type", ADL, "(asg b)\n", False, "type"),
    ("unknown-object", ADL, "(asg zz)\n", False, "unknown-object"),
    ("unknown-action", ADL, "(nope a)\n", False, "unknown-action"),
    ("upper-case", ADL, "(ASG A)\n", True, None),
    ("empty", ADL, "", False, "goal"),
    ("conditional-effect", ADL, "(light a)\n(pick a c)\n(inc c)\n", True, None),
    ("unmet-disjunction", ADL, "(pick a a)\n", False, "precondition"),
    ("simultaneous", ADL, "1: (light a)\n1: (light c)\n2: (pick a c)\n3: (inc c)\n", True, None),
    ("mutex-atom", ADL, "1: (light a)\n2: (light a)\n2: (pick a c)\n3: (inc c)\n", False,
     "mutex"),
    ("mutex-fluent", ADL, "0: (asg a)\n0: (inc a)\n", False, "mutex"),
    ("undefined-simultaneous", ADL, "0: (inc a)\n0: (low a)\n", False, "undefined-fluent"),
    # additive updates accumulate, concurrently and within one action (#168 review)
    ("additive-concurrent", ADL, "0: (h1 a)\n0: (h2 a)\n1: (need3 a)\n", True, None),
    ("additive-one-action", ADL, "(h12 a)\n(need3 a)\n", True, None),
    ("additive-sequential", ADL, "(h1 a)\n(h2 a)\n(need3 a)\n", True, None),
    ("numeric-read-vs-write", ADL, "1: (h12 a)\n2: (need3 a)\n2: (h1 a)\n", False, "mutex"),
    # a conditional branch counts only when its guard holds; a false guard
    # is not a read, a true one is; a guard's fluents must have values
    ("inactive-branch-no-mutex", ADL, "0: (maybe a)\n0: (unlit a)\n1: (asg a)\n", True, None),
    ("inactive-branch-undefined", ADL, "(wasg a)\n", True, None),
    ("false-guard-vs-write", ADL, "0: (maybe a)\n0: (lampon)\n1: (asg a)\n", True, None),
    ("true-guard-vs-write", ADL, "0: (lampon)\n1: (maybe a)\n1: (lampoff)\n2: (asg a)\n",
     False, "mutex"),
    ("active-branch-mutex", ADL, "0: (lampon)\n1: (maybe a)\n1: (unlit a)\n2: (asg a)\n",
     False, "mutex"),
    ("undefined-guard", ADL, "(gguard a)\n", False, "undefined-fluent"),
    # evaluation short-circuits: only fluents actually evaluated need values
    ("and-guard-short-circuit", ADL, "(sguard a)\n", True, None),
    ("or-guard-short-circuit", ADL, "(oguard a)\n", True, None),
    ("or-precondition-short-circuit", ADL, "(opre a)\n", True, None),
    ("and-guard-evaluated", ADL, "(lguard a)\n", False, "undefined-fluent"),
    # VAL's order: and evaluates atoms before comparisons, or keeps written order
    ("and-guard-numeric-first", ADL, "(nguard a)\n", True, None),
    ("not-and-numeric-first", ADL, "(nnot a)\n", True, None),
    ("nested-or-in-and", ADL, "(nnest a)\n", True, None),
    ("or-guard-numeric-first", ADL, "(oorder a)\n", False, "undefined-fluent"),
    # division by zero is IEEE (an infinity), not an error
    ("division-skipped", ADL, "(divskip a)\n", True, None),
    ("division-by-zero", ADL, "(divpre a)\n", True, None),
]
