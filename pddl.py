import sys
from antlr4 import *
from pddlpy.pddlLexer import pddlLexer
from pddlpy.pddlParser import pddlParser
from pddlpy.pddlListener import pddlListener


class Scope():
    def __init__(self):
        self.atoms = []
        self.negatoms = []

    def addatom(self, atom):
        self.atoms.append(atom)

    def addnegatom(self, atom):
        self.negatoms.append(atom)


class Operator():
    def __init__(self, name):
        self.operator_name = name
        self.variable_list = set()
        self.precondition_pos = set()
        self.precondition_neg = set()
        self.effect_pos = set()
        self.effect_neg = set()


class Domain(pddlListener):
    def __init__(self):
        self.operators = []
        self.scopes = []
        self.negativescopes = []

    def enterActionDef(self, ctx):
        opname = ctx.actionSymbol().getText()
        opvars = {}
        self.scopes.append(Operator(opname))

    def exitActionDef(self, ctx):
        action = self.scopes.pop()
        self.operators.append( action )
        
    def enterTypedVariableList(self, ctx):
        for v in ctx.VARIABLE():
            self.scopes[-1].variable_list.add(v.getText())

    def enterAtomicTermFormula(self, ctx):
        # print("-> termform")
        neg = self.negativescopes[-1]
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
        # print(pred)
        scope = self.scopes[-1]
        if not neg:
            scope.addatom(tuple(pred))
        else:
            scope.addnegatom(tuple(pred))

    def enterPrecondition(self, ctx):
        self.scopes.append(Scope())

    def exitPrecondition(self, ctx):
        scope = self.scopes.pop()
        self.scopes[-1].precondition_pos = set( scope.atoms )
        self.scopes[-1].precondition_neg = set( scope.negatoms )

    def enterEffect(self, ctx):
        self.scopes.append(Scope())

    def exitEffect(self, ctx):
        scope = self.scopes.pop()
        self.scopes[-1].effect_pos = set( scope.atoms )
        self.scopes[-1].effect_neg = set( scope.negatoms )

    def enterGoalDesc(self, ctx):
        negscope = False
        for c in ctx.getChildren():
            if c.getText() == 'not':
                negscope = True
                break
        self.negativescopes.append(negscope)

    def exitGoalDesc(self, ctx):
        self.negativescopes.pop()

    def enterPEffect(self, ctx):
        negscope = False
        for c in ctx.getChildren():
            if c.getText() == 'not':
                negscope = True
                break
        self.negativescopes.append(negscope)

    def exitPEffect(self, ctx):
        self.negativescopes.pop()


class Problem(pddlListener):

    def __init__(self):
        self.initialstate = []
        self.goals = []
        self.scopes = []

    def enterInit(self, ctx):
        self.scopes.append(Scope())

    def exitInit(self, ctx):
        self.initialstate = set( self.scopes.pop().atoms )

    def enterGoal(self, ctx):
        self.scopes.append(Scope())

    def exitGoal(self, ctx):
        self.goals = set( self.scopes.pop().atoms )

    def enterAtomicNameFormula(self, ctx):
        # print(ctx.__dir__())
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
        # print(pred)
        scope = self.scopes[-1]
        scope.addatom(tuple(pred))

    def enterAtomicTermFormula(self, ctx):
        # with a NOT!
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
        # print(pred)
        scope = self.scopes[-1]
        scope.addatom(tuple(pred))


def main(argv):
    # domain
    inp = FileStream(argv[1])
    lexer = pddlLexer(inp)
    stream = CommonTokenStream(lexer)
    parser = pddlParser(stream)
    tree = parser.domain()
    domain = Domain()
    walker = ParseTreeWalker()
    walker.walk(domain, tree)
    # problem
    inp = FileStream(argv[2])
    lexer = pddlLexer(inp)
    stream = CommonTokenStream(lexer)
    parser = pddlParser(stream)
    tree = parser.problem()
    problem = Problem()
    walker = ParseTreeWalker()
    walker.walk(problem, tree)
    # world
    print()
    print("DOMAIN")
    for op in domain.operators:
        print(op.operator_name)    
        print('\t', "vars", op.variable_list)
        print('\t', "pre+", op.precondition_pos)
        print('\t', "pre-",  op.precondition_neg)
        print('\t', "eff+", op.effect_pos)
        print('\t', "eff-", op.effect_neg)
    print()
    print("PROBLEM")
    print("init", problem.initialstate)
    print("goal", problem.goals)
    print()


if __name__ == '__main__':
    main(sys.argv)

