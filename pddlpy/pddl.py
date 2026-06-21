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

"""Core pddlpy object model and PDDL parser glue.

Parses PDDL domain/problem files via the generated ANTLR listeners into a
``DomainProblem`` exposing the initial state, goals, operators (instantaneous
and durative), numeric functions and the optimization metric. See
``docs/object-model.md`` for an overview and ``pddlpy.planning`` for the
solver layer built on top of this model.
"""
from __future__ import annotations

import operator as _operator
from typing import Any, Dict, Iterator, List, Optional, Sequence, Set, Tuple, cast

from antlr4 import CommonTokenStream, FileStream, ParseTreeWalker

from .binding import CartesianBinder, StaticPrunedBinder, VariableBinder
from .pddlLexer import pddlLexer
from .pddlListener import pddlListener
from .pddlParser import pddlParser

#: A binding of variable names to values, e.g. {"?x": "a"}.
VarVals = Dict[str, str]
#: A ground atom as a tuple of strings, e.g. ("on", "a", "b").
GroundAtom = Tuple[str, ...]
#: A numeric fluent valuation: ground function head -> value.
Valuation = Dict[GroundAtom, float]


class Atom():
    """A predicate applied to terms, e.g. ``(on ?x ?y)``.

    ``predicate`` is a sequence ``[name, *terms]``; terms beginning with ``?``
    are variables. ``ground(varvals)`` substitutes variables and returns a
    plain tuple. Note: ``Atom`` has no value equality — compare grounded atoms
    as tuples (see ``pddlpy.planning.atom_tuple``).
    """
    def __init__(self, predicate: Sequence[str]) -> None:
        self.predicate = predicate

    def __repr__(self) -> str:
        return str(tuple(self.predicate))

    def ground(self, varvals: VarVals) -> GroundAtom:
        g = [ varvals[v] if v in varvals else v for v in self.predicate ]
        return tuple(g)


# --------------------------------------------------------------------------
# Numeric fluents (#11): expression tree + numeric constraints/effects.
# Expressions ground variables like Atoms and evaluate against a valuation
# (a mapping from a ground function head tuple to a number).
# --------------------------------------------------------------------------

class Expr():
    """Base class for numeric expression nodes."""
    def ground(self, varvals: VarVals) -> "Expr":
        return self

    def value(self, valuation: Valuation) -> float:
        raise NotImplementedError  # pragma: no cover - abstract


class Num(Expr):
    """A numeric literal."""
    def __init__(self, value: Any) -> None:
        self.num = float(value)

    def value(self, valuation: Valuation) -> float:
        return self.num

    def __repr__(self) -> str:
        return repr(self.num)


class Fluent(Expr):
    """A (possibly ungrounded) function head, e.g. ('fuel', '?v')."""
    def __init__(self, head: Sequence[str]) -> None:
        self.head: GroundAtom = tuple(head)

    def ground(self, varvals: VarVals) -> "Fluent":
        return Fluent(tuple(varvals[s] if s in varvals else s for s in self.head))

    def value(self, valuation: Valuation) -> float:
        return valuation.get(self.head, 0.0)

    def __repr__(self) -> str:
        return str(self.head)


class BinOp(Expr):
    """A binary arithmetic operation (+, -, *, /)."""
    _ops = {'+': _operator.add, '-': _operator.sub,
            '*': _operator.mul, '/': _operator.truediv}

    def __init__(self, op: str, left: Expr, right: Expr) -> None:
        self.op = op
        self.left = left
        self.right = right

    def ground(self, varvals: VarVals) -> "BinOp":
        return BinOp(self.op, self.left.ground(varvals), self.right.ground(varvals))

    def value(self, valuation: Valuation) -> float:
        return self._ops[self.op](self.left.value(valuation), self.right.value(valuation))

    def __repr__(self) -> str:
        return "(%s %r %r)" % (self.op, self.left, self.right)


class Neg(Expr):
    """Unary minus."""
    def __init__(self, operand: Expr) -> None:
        self.operand = operand

    def ground(self, varvals: VarVals) -> "Neg":
        return Neg(self.operand.ground(varvals))

    def value(self, valuation: Valuation) -> float:
        return -self.operand.value(valuation)

    def __repr__(self) -> str:
        return "(- %r)" % (self.operand,)


class NumericConstraint():
    """A numeric precondition, e.g. (>= (fuel ?v) (fuel-cost ?from ?to))."""
    _cmp = {'>': _operator.gt, '<': _operator.lt, '=': _operator.eq,
            '>=': _operator.ge, '<=': _operator.le}

    def __init__(self, comp: str, lhs: Expr, rhs: Expr) -> None:
        self.comp = comp
        self.lhs = lhs
        self.rhs = rhs

    def ground(self, varvals: VarVals) -> "NumericConstraint":
        return NumericConstraint(self.comp, self.lhs.ground(varvals), self.rhs.ground(varvals))

    def holds(self, valuation: Valuation) -> bool:
        return self._cmp[self.comp](self.lhs.value(valuation), self.rhs.value(valuation))

    def __repr__(self) -> str:
        return "(%s %r %r)" % (self.comp, self.lhs, self.rhs)


class NumericEffect():
    """A numeric effect, e.g. (decrease (fuel ?v) (fuel-cost ?from ?to))."""
    def __init__(self, op: str, head: Fluent, expr: Expr) -> None:
        self.op = op
        self.head = head   # a Fluent
        self.expr = expr

    def ground(self, varvals: VarVals) -> "NumericEffect":
        return NumericEffect(self.op, self.head.ground(varvals), self.expr.ground(varvals))

    def apply(self, valuation: Valuation) -> Tuple[GroundAtom, float]:
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


def _parse_fhead(ctx: Any) -> GroundAtom:
    """Build a function-head tuple from an FHeadContext."""
    name = ctx.functionSymbol().getText()
    return tuple([name] + [t.getText() for t in ctx.term()])


def _nth_fexp(ctx: Any, i: int) -> Any:
    """Return the i-th fExp child of ctx. ANTLR generates a single-value
    accessor when fExp occurs once in a rule and a list accessor when it
    occurs more than once; this smooths over both."""
    fe = ctx.fExp()
    return fe[i] if isinstance(fe, list) else fe


def _parse_fexp(ctx: Any) -> Expr:
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


def _parse_fcomp(ctx: Any) -> NumericConstraint:
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
    def __init__(self, name: Optional[str]) -> None:
        self.operator_name = name
        self.variable_list: Dict[str, Optional[str]] = {}
        self.precondition_pos: set = set()
        self.precondition_neg: set = set()
        self.precondition_connective = 'and'
        self.effect_pos: set = set()
        self.effect_neg: set = set()
        self.precondition_num: List[NumericConstraint] = []
        self.effect_num: List[NumericEffect] = []

    def __str__(self) -> str:
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


class DurativeAction():
    """Represents a durative action (#23). Distinct from Operator: conditions
    are time-tagged 'at start' / 'over all' / 'at end', and effects 'at start'
    / 'at end'. Can be grounded or ungrounded.

    Attributes:
        operator_name -- the name of the durative action.
        variable_list -- {var: value} bindings (value None when ungrounded).
        duration -- the action duration as a float (from (= ?duration N)),
                    or None if not a simple numeric constraint.
        condition_pos / condition_neg -- dicts keyed by 'start'/'over'/'end',
                    each a set of (grounded: tuple / ungrounded: Atom) condition
                    atoms.
        effect_pos / effect_neg -- dicts keyed by 'start'/'end', each a set of
                    effect atoms to add / delete at that time point.
    """
    CONDITION_TIMES = ('start', 'over', 'end')
    EFFECT_TIMES = ('start', 'end')

    def __init__(self, name: Optional[str]) -> None:
        self.operator_name = name
        self.variable_list: Dict[str, Optional[str]] = {}
        self.duration: Optional[float] = None
        self.condition_pos: Dict[str, set] = {t: set() for t in self.CONDITION_TIMES}
        self.condition_neg: Dict[str, set] = {t: set() for t in self.CONDITION_TIMES}
        self.effect_pos: Dict[str, set] = {t: set() for t in self.EFFECT_TIMES}
        self.effect_neg: Dict[str, set] = {t: set() for t in self.EFFECT_TIMES}

    def ground(self, varvals: VarVals) -> "DurativeAction":
        """Return a grounded copy with variables substituted and atoms turned
        into tuples."""
        g = DurativeAction(self.operator_name)
        g.variable_list = dict(varvals)
        g.duration = self.duration
        for t in self.CONDITION_TIMES:
            g.condition_pos[t] = set(a.ground(varvals) for a in self.condition_pos[t])
            g.condition_neg[t] = set(a.ground(varvals) for a in self.condition_neg[t])
        for t in self.EFFECT_TIMES:
            g.effect_pos[t] = set(a.ground(varvals) for a in self.effect_pos[t])
            g.effect_neg[t] = set(a.ground(varvals) for a in self.effect_neg[t])
        return g

    def __str__(self) -> str:
        return ("Durative Action: %s\n\tVariables: %s\n\tDuration: %s\n\t"
                "Conditions (+): %s\n\tConditions (-): %s\n\t"
                "Effects (+): %s\n\tEffects (-): %s\n") % (
            self.operator_name, self.variable_list, self.duration,
            self.condition_pos, self.condition_neg,
            self.effect_pos, self.effect_neg)


class DomainListener(pddlListener):
    """ANTLR walk listener that builds the domain side of the model: types,
    constants, predicates, :functions, :requirements, and the (instantaneous
    and durative) action definitions."""
    def __init__(self):
        self.typesdef = False
        self.objects = {}
        # type hierarchy: maps each declared subtype to its direct supertype
        # (#22). E.g. (:types airport - location) yields {'airport': 'location'}.
        self.types = {}
        self.operators = {}
        self.durative_operators = {}
        self.scopes = []
        self.negativescopes = []
        self.requirements = set()
        self.predicates = set()  # declared predicate names (#12)
        self.functions = {}
        self._datimes = []      # stack of current 'start'/'over'/'end' tags

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
        self.scopes.append(Operator(opname))

    def exitActionDef(self, ctx):
        action = self.scopes.pop()
        self.operators[action.operator_name] = action

    # -- durative actions (#23) ------------------------------------------
    def enterDurativeActionDef(self, ctx):
        self.scopes.append(DurativeAction(ctx.actionSymbol().getText()))

    def exitDurativeActionDef(self, ctx):
        action = self.scopes.pop()
        self.durative_operators[action.operator_name] = action

    def enterSimpleDurationConstraint(self, ctx):
        # Capture (= ?duration N) / (<= ?duration N) etc. when N is a literal.
        durval = ctx.durValue()
        if durval is not None and durval.NUMBER() is not None:
            da = self.scopes[-1]
            if isinstance(da, DurativeAction):
                da.duration = float(durval.NUMBER().getText())

    def enterTimedGD(self, ctx):
        # (at start|end goalDesc) or (over all goalDesc): collect the condition
        # atoms into a fresh Scope tagged with the time point.
        if ctx.timeSpecifier() is not None:
            self._datimes.append(ctx.timeSpecifier().getText().lower())
        else:
            self._datimes.append('over')
        self.scopes.append(Scope())

    def exitTimedGD(self, ctx):
        scope = self.scopes.pop()
        time = self._datimes.pop()
        da = self.scopes[-1]
        da.condition_pos[time] |= set(scope.atoms)
        da.condition_neg[time] |= set(scope.negatoms)

    def enterTimedEffect(self, ctx):
        # (at start|end cEffect): collect the effect atoms into a fresh Scope.
        self._datimes.append(ctx.timeSpecifier().getText().lower())
        self.scopes.append(Scope())

    def exitTimedEffect(self, ctx):
        scope = self.scopes.pop()
        time = self._datimes.pop()
        da = self.scopes[-1]
        da.effect_pos[time] |= set(scope.atoms)
        da.effect_neg[time] |= set(scope.negatoms)

    def enterPredicatesDef(self, ctx):
        self.scopes.append(Operator(None))

    def exitPredicatesDef(self, ctx):
        self.scopes.pop()

    def enterAtomicFormulaSkeleton(self, ctx):
        # Record each declared predicate name (#12): a predicate that no action
        # ever modifies is static, which lets the grounder prune bindings.
        self.predicates.add(ctx.predicate().getText())

    def enterTypesDef(self, ctx):
        self.scopes.append(Obj())

    def exitTypesDef(self, ctx):
        self.typesdef = True
        # Keep the subtype -> supertype map (#22) instead of discarding it. The
        # Obj scope collected it as variable_list via enterTypedNameList; a type
        # with no declared parent maps to None.
        scope = self.scopes.pop()
        self.types = dict(scope.variable_list)

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
    """ANTLR walk listener that builds the problem side of the model: objects,
    the initial state (symbolic atoms and numeric assignments), the goal, and
    the optimization metric."""

    def __init__(self):
        self.objects = {}
        self.initialstate = []
        self.goals = []
        self.scopes = []
        self.init_numeric = {}
        self.metric = None

    def enterMetricSpec(self, ctx):
        # Capture the optimization metric, e.g. ('minimize', '(total-cost)').
        self.metric = (ctx.optimization().getText().lower(),
                       ctx.metricFExp().getText())

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

    def __init__(self, domainfile: str, problemfile: str,
                 binder: Optional[VariableBinder] = None) -> None:
        """Parses a PDDL domain and problem files and
        returns an object representing them.

        domainfile -- path for the PDDL domain file
        problemfile -- path for the PDDL problem file
        binder -- variable binding strategy for ground_operator (#12); defaults
                  to StaticPrunedBinder. Pass a custom VariableBinder, or set
                  the .binder attribute later, to override grounding.
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
        # Variable binding strategy used by ground_operator (#12).
        self.binder: VariableBinder = binder if binder is not None else StaticPrunedBinder()

    def operators(self) -> Any:
        """Returns an iterator of the names of the (instantaneous) actions
        defined in the domain file. Durative actions are listed separately by
        durative_operators().
        """
        return self.domain.operators.keys()

    def durative_operators(self) -> Any:
        """Returns an iterator of the names of the durative actions (#23)
        defined in the domain file.
        """
        return self.domain.durative_operators.keys()

    def requirements(self) -> set:
        """Returns the set of :requirements keywords declared in the domain
        (e.g. {':strips', ':typing'}), normalized to lowercase. Empty if the
        domain declares none.
        """
        return set(self.domain.requirements)

    def predicates(self) -> Set[str]:
        """Returns the set of predicate names declared in the domain's
        :predicates section, e.g. {'at', 'road', 'visited'}.
        """
        return set(self.domain.predicates)

    def functions(self) -> Dict[str, List[Tuple[str, Optional[str]]]]:
        """Returns a dict mapping each declared :functions name to its ordered
        list of (param_name, type) pairs. Empty if the domain declares none.
        """
        return dict(self.domain.functions)

    def initial_numeric(self) -> Valuation:
        """Returns a dict mapping each ground function head tuple to its
        initial numeric value, e.g. {('fuel', 'truck'): 100.0}.
        """
        return dict(self.problem.init_numeric)

    def metric(self) -> Optional[Tuple[str, str]]:
        """Returns the optimization metric as ``(optimization, expr_text)``,
        e.g. ``('minimize', '(total-cost)')``, or ``None`` if the problem
        declares no metric.
        """
        return self.problem.metric

    def ground_operator(self, op_name: str) -> Iterator[Operator]:
        """Returns an interator of Operator instances. Each item of the iterator
        is a grounded instance.

        returns -- An iterator of Operator instances.
        """
        op = self.domain.operators[op_name]
        for st in self.binder.bind( self, op ):
            gop = Operator(op_name)
            # grounded values are object names; widen to the field's lifted type
            gop.variable_list = cast(Dict[str, Optional[str]], st)
            gop.precondition_connective = op.precondition_connective
            gop.precondition_pos = set( [ a.ground( st ) for a in op.precondition_pos ] )
            gop.precondition_neg = set( [ a.ground( st ) for a in op.precondition_neg ] )
            gop.effect_pos = set( [ a.ground( st ) for a in op.effect_pos ] )
            gop.effect_neg = set( [ a.ground( st ) for a in op.effect_neg ] )
            gop.precondition_num = [ c.ground( st ) for c in op.precondition_num ]
            gop.effect_num = [ e.ground( st ) for e in op.effect_num ]
            yield gop

    def ground_durative_operator(self, op_name: str) -> Iterator[DurativeAction]:
        """Returns an iterator of grounded DurativeAction instances (#23).

        Durative actions always use the cartesian binder: their conditions are
        time-tagged and static-precondition pruning does not apply.
        """
        op = self.domain.durative_operators[op_name]
        for st in CartesianBinder().bind( self, op ):
            yield op.ground( st )

    def _is_subtype(self, ot, t):
        """True if object-type ``ot`` satisfies a parameter typed ``t`` (#22):
        either they are equal or ``ot`` is a transitive subtype of ``t``. The
        equality check comes first so untyped domains (``None == None``) and
        flat-typed domains keep working unchanged.
        """
        # An untyped parameter (t is None) binds only untyped objects, matching
        # the original exact-match behaviour; do not let a typed object climb to
        # the implicit None root and match an untyped parameter.
        if t is None:
            return ot is None
        seen = set()
        while ot is not None and ot not in seen:
            if ot == t:
                return True
            seen.add(ot)
            ot = self.domain.types.get(ot)
        return False

    def candidate_objects(self, t) -> List[str]:
        """Returns the objects that can bind a parameter of type ``t``: any
        object whose type is ``t`` or a (transitive) subtype of it (#22).
        Used by the variable binders (#12).
        """
        return [ k for k,v in self.worldobjects().items() if self._is_subtype(v, t) ]

    def static_predicates(self) -> set:
        """Returns the set of static predicate names (#12): predicates declared
        in the domain that no action (instantaneous or durative) ever adds or
        deletes. Their truth is fixed by the initial state, so the grounder can
        use them to prune bindings that can never become applicable.
        """
        modified = set()
        for op in self.domain.operators.values():
            for a in op.effect_pos | op.effect_neg:
                modified.add(a.predicate[0])
        for da in self.domain.durative_operators.values():
            for time in da.EFFECT_TIMES:
                for a in da.effect_pos[time] | da.effect_neg[time]:
                    modified.add(a.predicate[0])
        return set(self.domain.predicates) - modified

    def types(self) -> Dict[str, Optional[str]]:
        """Returns the declared type hierarchy as a dict mapping each subtype to
        its direct supertype (#22), e.g. ``{'airport': 'location', 'location':
        'object'}``. A type with no declared parent maps to ``None``. Empty if
        the domain declares no ``:types``.
        """
        return dict(self.domain.types)

    def subtypes_of(self, t: str) -> set:
        """Returns the set of all transitive subtypes of ``t`` (#22), excluding
        ``t`` itself. E.g. for the logistics hierarchy ``subtypes_of('physobj')``
        is ``{'package', 'vehicle', 'truck', 'airplane'}``.
        """
        hierarchy = self.domain.types
        result = set()
        changed = True
        while changed:
            changed = False
            for sub, sup in hierarchy.items():
                if sub in result:
                    continue
                if sup == t or sup in result:
                    result.add(sub)
                    changed = True
        return result

    def initialstate(self) -> set:
        """Returns a set of atoms (Atom objects) corresponding to the initial
        state defined in the problem file.
        """
        return self.problem.initialstate

    def goals(self) -> set:
        """Returns a set of atoms (Atom objects) corresponding to the goals
        defined in the problem file.
        """
        return self.problem.goals

    def worldobjects(self) -> Dict[str, Optional[str]]:
        """Returns a dictionary of key value pairs where the key is the name of
        an object and the value is it's type (None in case is untyped.)
        """
        return dict( self.domain.objects.items() | self.problem.objects.items() )



if __name__ == '__main__':  # pragma: no cover
    pass

