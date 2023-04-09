#!/usr/bin/python
# -*- coding: utf-8 -*-

#
# Copyright 2015 Hernán M. Foffani
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#

from antlr4 import *
from .pddlLexer import pddlLexer
from .pddlParser import pddlParser
from .pddlListener import pddlListener

import itertools


class Atom():
    def __init__(self, predicate):
        self.predicate = predicate

    def __repr__(self):
        return str(tuple(self.predicate))

    def ground(self, varvals):
        g = [ varvals[v] if v in varvals else v for v in self.predicate ]
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
    """Represents and action. Can be grounded or ungrounded.
    Ungrounded operators have a '?' in names (unbound variables).
    Attributes:

        operator_name -- the name of operator (action in the domain.)
        variable_list -- a dictionary of key-value pairs where the key
                         is the variable name (with the '?') and the
                         value is the value of it when the operator is
                         grounded.
        precondition_pos -- a set of atoms corresponding to the
                            positive preconditions.
        precondition_neg -- a set of atoms corresponding to the
                            negative preconditions.
        effect_pos -- a set of atoms to add.
        effect_neg -- a set of atoms to delete.
    """
    def __init__(self, name):
        self.operator_name = name
        self.variable_list = {}
        self.precondition_pos = set()
        self.precondition_neg = set()
        self.effect_pos = set()
        self.effect_neg = set()

    def __str__(self):
        templ = "Operator Name: %s\n\tVariables: %s\n\t" + \
                "Positive Preconditions: %s\n\t" + \
                "Negative Preconditions: %s\n\t" + \
                "Positive Effects: %s\n\t" + \
                "Negative Effects: %s\n"
        return templ % ( self.operator_name, self.variable_list,
                         self.precondition_pos, self.precondition_neg,
                         self.effect_pos, self.effect_neg)


class DomainListener(pddlListener):
    def __init__(self):
        self.typesdef = False
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
        self.scopes.append(Operator(None))

    def exitPredicatesDef(self, ctx):
        dummyop = self.scopes.pop()

    def enterTypesDef(self, ctx):
        self.scopes.append(Obj())

    def exitTypesDef(self, ctx):
        self.typesdef = True
        self.scopes.pop()

    def enterTypedVariableList(self, ctx):
        # print("-> tvar")
        for v in ctx.VARIABLE():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeVarList():
            t = vs.r_type().getText()
            for v in vs.VARIABLE():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t

    def enterAtomicTermFormula(self, ctx):
        # print("-> terf")
        neg = self.negativescopes[-1]
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
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
        negscope = bool(self.negativescopes and self.negativescopes[-1])
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
        # print("-> tnam")
        for v in ctx.name():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.name():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t

    def enterConstantsDef(self, ctx):
        self.scopes.append(Obj())

    def exitConstantsDef(self, ctx):
        scope = self.scopes.pop()
        self.objects = scope.variable_list

    def exitDomain(self, ctx):
        if not self.objects and not self.typesdef:
            vs = set()
            for opn, oper in self.operators.items():
                alls = oper.precondition_pos | oper.precondition_neg | oper.effect_pos | oper.effect_neg
                for a in alls:
                    for s in a.predicate:
                        if s[0] != '?':
                            vs.add( (s, None) )
            self.objects = dict( vs)


class ProblemListener(pddlListener):

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
        pred = []
        for c in ctx.getChildren():
            n = c.getText()
            if n == '(' or n == ')':
                continue
            pred.append(n)
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
        scope = self.scopes[-1]
        scope.addatom(Atom(pred))

    def enterTypedNameList(self, ctx):
        for v in ctx.name():
            vname = v.getText()
            self.scopes[-1].variable_list[v.getText()] = None
        for vs in ctx.singleTypeNameList():
            t = vs.r_type().getText()
            for v in vs.name():
                vname = v.getText()
                self.scopes[-1].variable_list[vname] = t

    def enterObjectDecl(self, ctx):
        self.scopes.append(Obj())

    def exitObjectDecl(self, ctx):
        scope = self.scopes.pop()
        self.objects = scope.variable_list

    def exitProblem(self, ctx):
        if not self.objects:
            vs = set()
            for a in self.initialstate:
                for s in a.predicate:
                    vs.add( (s, None) )
            for a in self.goals:
                for s in a.predicate:
                    vs.add( (s, None) )
            self.objects = dict( vs )


class DomainProblem():

    def __init__(self, domainfile, problemfile):
        """Parses a PDDL domain and problem files and
        returns an object representing them.

        domainfile -- path for the PDDL domain file
        problemfile -- path for the PDDL problem file
        """
        # domain
        inp = FileStream(domainfile)
        lexer = pddlLexer(inp)
        stream = CommonTokenStream(lexer)
        parser = pddlParser(stream)
        tree = parser.domain()
        self.domain = DomainListener()
        walker = ParseTreeWalker()
        walker.walk(self.domain, tree)
        # problem
        inp = FileStream(problemfile)
        lexer = pddlLexer(inp)
        stream = CommonTokenStream(lexer)
        parser = pddlParser(stream)
        tree = parser.problem()
        self.problem = ProblemListener()
        walker = ParseTreeWalker()
        walker.walk(self.problem, tree)
        # variable ground space for each operator.
        # a dict where keys are op names and values
        # a dict where keys are var names and values
        # a list of possible symbols.
        self.vargroundspace = {}

    def operators(self):
        """Returns an iterator of the names of the actions defined in
        the domain file.
        """
        return self.domain.operators.keys()

    def ground_operator(self, op_name):
        """Returns an interator of Operator instances. Each item of the iterator
        is a grounded instance.

        returns -- An iterator of Operator instances.
        """
        op = self.domain.operators[op_name]
        self._set_operator_groundspace( op_name, op.variable_list.items() )
        for ground in self._instantiate( op_name ):
            # print('grounded', ground)
            st = dict(ground)
            gop = Operator(op_name)
            gop.variable_list = st
            gop.precondition_pos = set( [ a.ground( st ) for a in op.precondition_pos ] )
            gop.precondition_neg = set( [ a.ground( st ) for a in op.precondition_neg ] )
            gop.effect_pos = set( [ a.ground( st ) for a in op.effect_pos ] )
            gop.effect_neg = set( [ a.ground( st ) for a in op.effect_neg ] )
            yield gop

    def _typesymbols(self, t):
        return ( k for k,v in self.worldobjects().items() if v == t )

    def _set_operator_groundspace(self, opname, variables):
        # cache the variables ground space for each operator.
        if opname not in self.vargroundspace:
            d = self.vargroundspace.setdefault(opname, {})
            for vname, t in variables:
                for symb in self._typesymbols(t):
                    d.setdefault(vname, []).append(symb)

    def _instantiate(self, opname):
        d = self.vargroundspace[opname]
        # expands the dict to something like:
        #[ [('?x1','A'),('?x1','B')..], [('?x2','M'),('?x2','N')..],..]
        expanded = [ [ (vname, symb) for symb in d[vname] ] for vname in d ]
        # cartesian product.
        return itertools.product(*expanded)

    def initialstate(self):
        """Returns a set of atoms (tuples of strings) corresponding to the intial
        state defined in the problem file.
        """
        return self.problem.initialstate

    def goals(self):
        """Returns a set of atoms (tuples of strings) corresponding to the goals
        defined in the problem file.
        """
        return self.problem.goals

    def worldobjects(self):
        """Returns a dictionary of key value pairs where the key is the name of
        an object and the value is it's type (None in case is untyped.)
        """
        return dict( self.domain.objects.items() | self.problem.objects.items() )



if __name__ == '__main__':
    pass

