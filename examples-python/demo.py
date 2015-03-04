import sys
from  pddlpy import DomainProblem

def main(argv):
    domprob = DomainProblem(argv[1], argv[2])
    print()
    print("DOMAIN PROBLEM")
    print("objects")
    print("\t", domprob.worldobjects())
    print("operators")
    print("\t", list( domprob.operators() ))
    print("init",)
    print("\t", domprob.initialstate())
    print("goal",)
    print("\t", domprob.goals())

    print()
    op = "move"
    #op = "op2"
    print("ground for operator", op, "applicable if (adjacent loc1 loc2)")
    for o in domprob.ground_operator(op):
        if ("adjacent","loc1","loc2") in o.precondition_pos:
            print()
            print( "\tvars", o.variable_list )
            print( "\tpre+", o.precondition_pos )
            print( "\tpre-", o.precondition_neg )
            print( "\teff+", o.effect_pos )
            print( "\teff-", o.effect_neg )


if __name__ == '__main__':
    main(sys.argv)

