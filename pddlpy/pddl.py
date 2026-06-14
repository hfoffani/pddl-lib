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
import operator as _operator


class Atom():
    def __init__(self, predicate):
        self.predicate = predicate

    def __repr__(self):
        return str(tuple(self.predicate))

    def ground(self, varvals):
        g = [ varvals[v] if v in varvals else v for v in self.predicate ]
        return tuple(g)


# --------------------------------------------------------------------------
# Numeric fluents (#11): expression tree + numeric constraints/effects.
# Expressions ground variables like Atoms and evaluate against a valuation
# (a mapping from a ground function head tuple to a number).
# --------------------------------------------------------------------------

class Expr():
    """Base class for numeric expression nodes."""
    def ground(self, varvals):
        return self

    def value(self, valuation):
        raise NotImplementedError


class Num(Expr):
    """A numeric literal."""
    def __init__(self, value):
        self.num = float(value)

    def value(self, valuation):
        return self.num

    def __repr__(self):
        return repr(self.num)


class Fluent(Expr):
    """A (possibly ungrounded) function head, e.g. ('fuel', '?v')."""
    def __init__(self, head):
        self.head = tuple(head)

    def ground(self, varvals):
        return Fluent(tuple(varvals[s] if s in varvals else s for s in self.head))

    def value(self, valuation):
        return valuation.get(self.head, 0.0)

    def __repr__(self):
        return str(self.head)


class BinOp(Expr):
    """A binary arithmetic operation (+, -, *, /)."""
    _ops = {'+': _operator.add, '-': _operator.sub,
            '*': _operator.mul, '/': _operator.truediv}

    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def ground(self, varvals):
        return BinOp(self.op, self.left.ground(varvals), self.right.ground(varvals))

    def value(self, valuation):
        return self._ops[self.op](self.left.value(valuation), self.right.value(valuation))

    def __repr__(self):
        return "(%s %r %r)" % (self.op, self.left, self.right)


class Neg(Expr):
    """Unary minus."""
    def __init__(self, operand):
        self.operand = operand

    def ground(self, varvals):
        return Neg(self.operand.ground(varvals))

    def value(self, valuation):
        return -self.operand.value(valuation)

    def __repr__(self):
        return "(- %r)" % (self.operand,)


class NumericConstraint():
    """A numeric precondition, e.g. (>= (fuel ?v) (fuel-cost ?from ?to))."""
    _cmp = {'>': _operator.gt, '<': _operator.lt, '=': _operator.eq,
            '>=': _operator.ge, '<=': _operator.le}

    def __init__(self, comp, lhs, rhs):
        self.comp = comp
        self.lhs = lhs
        self.rhs = rhs

    def ground(self, varvals):
        return NumericConstraint(self.comp, self.lhs.ground(varvals), self.rhs.ground(varvals))

    def holds(self, valuation):
        return self._cmp[self.comp](self.lhs.value(valuation), self.rhs.value(valuation))

    def __repr__(self):
        return "(%s %r %r)" % (self.comp, self.lhs, self.rhs)


class NumericEffect():
    """A numeric effect, e.g. (decrease (fuel ?v) (fuel-cost ?from ?to))."""
    def __init__(self, op, head, expr):
        self.op = op
        self.head = head   # a Fluent
        self.expr = expr

    def ground(self, varvals):
        return NumericEffect(self.op, self.head.ground(varvals), self.expr.ground(varvals))

    def apply(self, valuation):
        """Return (ground_head_tuple, new_value) given the current valuation."""
        key = self.head.head
        rhs = self.expr.value(valuation)
        if self.op == 'assign':
            new = rhs
        elif self.op == 'increase':
            new = valuation.get(key, 0.0) + rhs
        elif self.op == 'decrease':
            new = valuation.get(key, 0.0) - rhs
        elif self.op == 'scale-up':
            new = valuation.get(key, 0.0) * rhs
        elif self.op == 'scale-down':
            new = valuation.get(key, 0.0) / rhs
        else:  # pragma: no cover - grammar restricts assignOp to the above
            raise ValueError("unknown assign op: %s" % self.op)
        return key, new

    def __repr__(self):
        return "(%s %r %r)" % (self.op, self.head, self.expr)


def _parse_fhead(ctx):
    """Build a function-head tuple from an FHeadContext."""
    name = ctx.functionSymbol().getText()
    return tuple([name] + [t.getText() for t in ctx.term()])


def _nth_fexp(ctx, i):
    """Return the i-th fExp child of ctx. ANTLR generates a single-value
    accessor when fExp occurs once in a rule and a list accessor when it
    occurs more than once; this smooths over both."""
    fe = ctx.fExp()
    return fe[i] if isinstance(fe, list) else fe


def _parse_fexp(ctx):
    """Build an Expr from an FExpContext."""
    if ctx.NUMBER() is not None:
        return Num(ctx.NUMBER().getText())
    if ctx.fHead() is not None:
        return Fluent(_parse_fhead(ctx.fHead()))
    if ctx.binaryOp() is not None:
        return BinOp(ctx.binaryOp().getText(),
                     _parse_fexp(_nth_fexp(ctx, 0)),
                     _parse_fexp(ctx.fExp2().fExp()))
    # '(' '-' fExp ')'
    return Neg(_parse_fexp(_nth_fexp(ctx, 0)))


def _parse_fcomp(ctx):
    """Build a NumericConstraint from an FCompContext."""
    return NumericConstraint(ctx.binaryComp().getText(),
                             _parse_fexp(_nth_fexp(ctx, 0)),
                             _parse_fexp(_nth_fexp(ctx, 1)))


class Scope():
    def __init__(self):
        self.atoms = []
        self.negatoms = []
        self.numerics = []      # NumericConstraint (preconditions)
        self.numeffects = []    # NumericEffect
        self.variable_list = {}

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
        precondition_connective -- the top-level logical connective of the
                            precondition, either 'and' (the default) or 'or'.
                            For a disjunctive precondition this is 'or' so that
                            it is no longer silently modeled as a conjunction
                            (#13). Note: full and/or/not tree evaluation is not
                            yet implemented; the atoms are still flattened into
                            the positive/negative sets.
        effect_pos -- a set of atoms to add.
        effect_neg -- a set of atoms to delete.
        precondition_num -- a list of NumericConstraint numeric preconditions
                            (#11), e.g. (>= (fuel ?v) 10).
        effect_num -- a list of NumericEffect numeric effects (#11),
                            e.g. (decrease (fuel ?v) 5).
    """
    def __init__(self, name):
        self.operator_name = name
        self.variable_list = {}
        self.precondition_pos = set()
        self.precondition_neg = set()
        self.precondition_connective = 'and'
        self.effect_pos = set()
        self.effect_neg = set()
        self.precondition_num = []
        self.effect_num = []

    def __str__(self):
        templ = "Operator Name: %s\n\tVariables: %s\n\t" + \
                "Precondition Connective: %s\n\t" + \
                "Positive Preconditions: %s\n\t" + \
                "Negative Preconditions: %s\n\t" + \
                "Positive Effects: %s\n\t" + \
                "Negative Effects: %s\n"
        return templ % ( self.operator_name, self.variable_list,
                         self.precondition_connective,
                         self.precondition_pos, self.precondition_neg,
                         self.effect_pos, self.effect_neg)


class DomainListener(pddlListener):
    def __init__(self):
        self.typesdef = False
        self.objects = {}
        self.operators = {}
        self.scopes = []
        self.negativescopes = []
        self.requirements = set()
        self.functions = {}

    def enterRequireDef(self, ctx):
        # Capture declared :requirements (e.g. ':strips', ':typing').
        # Keywords are case-insensitive, so normalize to lowercase.
        for rk in ctx.REQUIRE_KEY():
            self.requirements.add(rk.getText().lower())

    def enterFunctionsDef(self, ctx):
        # Push a throwaway scope so typedVariableList (function parameters)
        # has somewhere to write without crashing the listener.
        self.scopes.append(Obj())

    def exitFunctionsDef(self, ctx):
        self.scopes.pop()

    def enterAtomicFunctionSkeleton(self, ctx):
        # Capture a :functions declaration: name -> ordered list of param types.
        name = ctx.functionSymbol().getText()
        tvl = ctx.typedVariableList()
        params = []
        for v in tvl.VARIABLE():
            params.append((v.getText(), None))
        for vs in tvl.singleTypeVarList():
            t = vs.r_type().getText()
            for v in vs.VARIABLE():
                params.append((v.getText(), t))
        self.functions[name] = params

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
        self.scopes[-1].precondition_connective = self._connective( ctx.goalDesc() )
        self.scopes[-1].precondition_num = list( scope.numerics )

    def enterFComp(self, ctx):
        # A numeric comparison precondition, e.g. (>= (fuel ?v) 10).
        scope = self.scopes[-1]
        if hasattr(scope, 'numerics'):
            scope.numerics.append(_parse_fcomp(ctx))

    @staticmethod
    def _connective(goaldesc_ctx):
        # Top-level connective of a goalDesc: 'and' (default), or 'or' for a
        # disjunctive precondition (#13). Keywords are case-insensitive.
        if goaldesc_ctx is not None and goaldesc_ctx.getChildCount() >= 2:
            tok = goaldesc_ctx.getChild(1).getText().lower()
            if tok == 'or':
                return 'or'
        return 'and'

    def enterEffect(self, ctx):
        self.scopes.append(Scope())

    def exitEffect(self, ctx):
        scope = self.scopes.pop()
        self.scopes[-1].effect_pos = set( scope.atoms )
        self.scopes[-1].effect_neg = set( scope.negatoms )
        self.scopes[-1].effect_num = list( scope.numeffects )

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
        # A numeric assignment effect, e.g. (decrease (fuel ?v) 5).
        if ctx.assignOp() is not None:
            scope = self.scopes[-1]
            if hasattr(scope, 'numeffects'):
                effect = NumericEffect(ctx.assignOp().getText().lower(),
                                       Fluent(_parse_fhead(ctx.fHead())),
                                       _parse_fexp(_nth_fexp(ctx, 0)))
                scope.numeffects.append(effect)
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
        self.init_numeric = {}

    def enterInit(self, ctx):
        self.scopes.append(Scope())

    def exitInit(self, ctx):
        self.initialstate = set( self.scopes.pop().atoms )

    def enterInitEl(self, ctx):
        # Numeric init assignment: (= (fhead ...) NUMBER).
        if ctx.fHead() is not None and ctx.NUMBER() is not None:
            head = _parse_fhead(ctx.fHead())
            self.init_numeric[head] = float(ctx.NUMBER().getText())

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

    def requirements(self):
        """Returns the set of :requirements keywords declared in the domain
        (e.g. {':strips', ':typing'}), normalized to lowercase. Empty if the
        domain declares none.
        """
        return set(self.domain.requirements)

    def functions(self):
        """Returns a dict mapping each declared :functions name to its ordered
        list of (param_name, type) pairs. Empty if the domain declares none.
        """
        return dict(self.domain.functions)

    def initial_numeric(self):
        """Returns a dict mapping each ground function head tuple to its
        initial numeric value, e.g. {('fuel', 'truck'): 100.0}.
        """
        return dict(self.problem.init_numeric)

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
            gop.precondition_connective = op.precondition_connective
            gop.precondition_pos = set( [ a.ground( st ) for a in op.precondition_pos ] )
            gop.precondition_neg = set( [ a.ground( st ) for a in op.precondition_neg ] )
            gop.effect_pos = set( [ a.ground( st ) for a in op.effect_pos ] )
            gop.effect_neg = set( [ a.ground( st ) for a in op.effect_neg ] )
            gop.precondition_num = [ c.ground( st ) for c in op.precondition_num ]
            gop.effect_num = [ e.ground( st ) for e in op.effect_num ]
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



if __name__ == '__main__':  # pragma: no cover
    pass

