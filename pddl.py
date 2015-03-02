import sys
from antlr4 import *
from pddlpy.pddlLexer import pddlLexer
from pddlpy.pddlParser import pddlParser
from pddlpy.pddlListener import pddlListener



class Atom():
    def __init__(self, predicate):
        self.predicate = predicate

    def __repr__(self):
        return str(tuple(self.predicate))

    def ground(self, varvals):
        g = []
        for v in self.predicate:
            g.append( varvals[v] if v in varvals else v )
        return tuple(g)

class Scope():
    def __init__(self):
        self.atoms = []
        self.negatoms = []

    def addatom(self, atom):
        self.atoms.append(atom)

    def addnegatom(self, atom):
        self.negatoms.append(atom)


class Obj():
    def __init__(self):
        self.variable_list = {}

class Operator():
    def __init__(self, name):
        self.operator_name = name
        self.variable_list = {}
        self.precondition_pos = set()
        self.precondition_neg = set()
        self.effect_pos = set()
        self.effect_neg = set()


class Domain(pddlListener):
    def __init__(self):
        self.objects = {}
        self.operators = {}
        self.scopes = []
        self.negativescopes = []

    def enterActionDef(self, ctx):
        opname = ctx.actionSymbol().getText()
        opvars = {}
        self.scopes.append(Operator(opname))

    def exitActionDef(self, ctx):
        action = self.scopes.pop()
        self.operators[action.operator_name] = action

    def enterPredicatesDef(self, ctx):
        self.scopes.append(Operator('dummy'))

    def exitPredicatesDef(self, ctx):
        self.scopes.pop()

    def enterTypedVariableList(self, ctx):
        for v in ctx.VARIABLE():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeVarList():
            t = vs.r_type().getText()
            for v in vs.VARIABLE():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t

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
            scope.addatom(Atom(pred))
        else:
            scope.addnegatom(Atom(pred))

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

    def enterTypedNameList(self, ctx):
        for v in ctx.NAME():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.NAME():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t

    def enterConstantsDef(self, ctx):
        self.scopes.append(Obj())

    def exitConstantsDef(self, ctx):
        scope = self.scopes.pop()
        self.objects = scope.variable_list

    def enterTypesDef(self, ctx):
        self.scopes.append(Obj())

    def exitTypesDef(self, ctx):
        scope = self.scopes.pop()


class Problem(pddlListener):

    def __init__(self):
        self.objects = {}
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
        scope.addatom(Atom(pred))

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
        scope.addatom(Atom(pred))

    def enterTypedNameList(self, ctx):
        for v in ctx.NAME():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.NAME():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t

    def enterObjectDecl(self, ctx):
        self.scopes.append(Obj())

    def exitObjectDecl(self, ctx):
        scope = self.scopes.pop()
        self.objects = scope.variable_list


class DomainProblem():

    def __init__(self, domainfile, problemfile):
        # domain
        inp = FileStream(domainfile)
        lexer = pddlLexer(inp)
        stream = CommonTokenStream(lexer)
        parser = pddlParser(stream)
        tree = parser.domain()
        self.domain = Domain()
        walker = ParseTreeWalker()
        walker.walk(self.domain, tree)
        # problem
        inp = FileStream(problemfile)
        lexer = pddlLexer(inp)
        stream = CommonTokenStream(lexer)
        parser = pddlParser(stream)
        tree = parser.problem()
        self.problem = Problem()
        walker = ParseTreeWalker()
        walker.walk(self.problem, tree)

    def operators(self):
        return self.domain.operators.keys()

    def ground_operator(self, op_name):
        op = self.domain.operators[op_name]
        gop = Operator(op_name)
        for ground in self._instantiate( op.variable_list.items() ):
            st = dict(ground)
            gop.variable_list = st
            gop.precondition_pos = set( [ a.ground( st ) for a in op.precondition_pos ] )
            gop.precondition_neg = set( [ a.ground( st ) for a in op.precondition_neg ] )
            gop.effect_pos = set( [ a.ground( st ) for a in op.effect_pos ] )
            gop.effect_neg = set( [ a.ground( st ) for a in op.effect_neg ] )
            yield gop

    def _typesymbols(self, t):
        return ( k for k,v in self.worldobjects().items() if v == t )

    def _instantiate(self, variables):
        import itertools
        alls = []
        for vname, t in variables:
            c = []
            for symb in self._typesymbols(t):
                c.append((vname, symb) )
            alls.append(c)
        return itertools.product(*alls)

    def initialstate(self):
        return self.problem.initialstate

    def goals(self):
        return self.problem.goals

    def worldobjects(self):
        return dict( self.domain.objects.items() | self.problem.objects.items() )


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

