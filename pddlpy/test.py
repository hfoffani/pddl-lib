import unittest
from pddlpy import DomainProblem

class TestStringMethods(unittest.TestCase):
    domainfile = "examples-pddl/domain-0%d.pddl" % 1
    problemfile = "examples-pddl/problem-0%d.pddl" % 1

    def test_ground(self):
        domprob = DomainProblem(self.domainfile, self.problemfile)
        freeop = domprob.domain.operators["op2"]
        all_grounded_opers = domprob.ground_operator("op2")
        for gop in all_grounded_opers:
            if gop.precondition_pos == set( [('S','R','C'),('S','R','S')] ):
                self.assertTrue(True)
                return
        self.assertFalse("Missed a value")

if __name__ == '__main__':
    unittest.main()

