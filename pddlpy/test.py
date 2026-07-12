import unittest

from pddlpy import DomainProblem


class TestStringMethods(unittest.TestCase):
    domainfile = "examples-pddl/domain-0%d.pddl" % 1
    problemfile = "examples-pddl/problem-0%d.pddl" % 1

    def test_ground(self):
        domprob = DomainProblem(self.domainfile, self.problemfile)
        all_grounded_opers = domprob.ground_operator("op2")
        for gop in all_grounded_opers:
            if gop.precondition_pos == set( [('S','B','C'),('S','B','A')] ):
                self.assertTrue(True)
                return
        self.assertFalse("Missed a value")

    def test_worldobjects_excludes_predicate_names(self):
        # Untyped domain/problem without :objects: world objects come from
        # the constants in :init and :goal, never from predicate names.
        domprob = DomainProblem(self.domainfile, self.problemfile)
        self.assertEqual(domprob.worldobjects(),
                         {'A': None, 'B': None, 'C': None})

if __name__ == '__main__':
    unittest.main()

