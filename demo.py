import sys
import pddl

def main(argv):
    domprob = pddl.DomainProblem(argv[1], argv[2])
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
    print("ground for operator", op)
    for o in domprob.ground_operator(op):
        print()
        print( "\tvars", o.variable_list )
        print( "\tpre+", o.precondition_pos )
        print( "\tpre-", o.precondition_neg )
        print( "\teff+", o.effect_pos )
        print( "\teff-", o.effect_neg )


if __name__ == '__main__':
    main(sys.argv)

