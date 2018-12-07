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
from enum import Enum


def list2str(list_):
    return ", ".join([str(elem) for elem in list_])


def get_operator(ctx, operator_cls):
    from antlr4.tree.Tree import TerminalNodeImpl
    operator_name_list = []
    for child in ctx.getChildren():
        if child.getText() in ["(", ")"]:
            continue
        elif isinstance(child, (TerminalNodeImpl,
                                pddlParser.TimeSpecifierContext, pddlParser.IntervalContext, pddlParser.DurOpContext)):
            operator_name_list.append(child.getText())
        else:
            break
    if not operator_name_list:
        return None
    operator_name = " ".join(operator_name_list)
    return operator_cls(operator_name)


class Atom(object):

    def __init__(self, predicate, variables=None):
        self.predicate = None
        self.variables = []
        if isinstance(predicate, pddlParser.AtomicTermFormulaContext):
            self._init_from_ctx(predicate)
        else:
            self.predicate = predicate
            self.variables = list(variables)

    def _init_from_ctx(self, ctx):
        from antlr4.tree.Tree import TerminalNodeImpl
        for child in ctx.getChildren():
            if isinstance(child, TerminalNodeImpl):
                continue
            if isinstance(child, pddlParser.PredicateContext):
                self.predicate = child.getText()
            else:
                self.variables.append(child.getText())

    def __repr__(self):
        return "{} {}".format(self.predicate, list2str(self.variables))

    def __eq__(self, other):
        return isinstance(other, Atom) and other.predicate == self.predicate and other.variables == self.variables

    def ground(self, varvals):
        g = [ varvals[v] if v in varvals else v for v in self.predicate ]
        return tuple(g)


class Scope(dict):
    def __init__(self):
        super(Scope, self).__init__()

    def add_by_type(self, item):
        type_ = type(item)
        if type_ not in self:
            self[type_] = []
        self[type_].append(item)

    def __missing__(self, key):
        return []


class Obj():
    def __init__(self):
        self.variable_list = {}

    def __str__(self):
        return ", ".join(["{}={}".format(name, value) if value else name
                          for name, value in self.variable_list.items()])

    def __eq__(self, other):
        return isinstance(other, Obj) and self.variable_list == other.variable_list


class GoalOperator(Enum):
    AND = "and"
    OR = "or"
    NOT = "not"
    IMPLY = "imply"
    EXISTS = "exists"
    FORALL = "forall"
    AT_START = "at start"
    AT_END = "at end"
    OVER_ALL = "over all"


class Goal(object):
    atom = None
    operator = None
    subgoals = None
    obj = None

    def __init__(self, operator=None, subgoals=None, atom=None, obj=None):
        self.operator = operator
        if atom:
            assert isinstance(atom, Atom)
            self.atom = atom
        elif operator in [GoalOperator.AND, GoalOperator.OR]:
            assert hasattr(subgoals, "__iter__") and all(isinstance(goal, Goal) for goal in subgoals)
            self.subgoals = tuple(subgoals)
        elif operator == GoalOperator.NOT:
            assert isinstance(subgoals, Goal)
            self.subgoals = (subgoals,)
        elif operator == GoalOperator.IMPLY:
            assert hasattr(subgoals, "__len__") and len(subgoals) == 2 and all(isinstance(goal, Goal) for goal in subgoals)
            self.subgoals = tuple(subgoals)
        elif operator in [GoalOperator.EXISTS, GoalOperator.FORALL]:
            assert isinstance(obj, Obj) and isinstance(subgoals, Goal)
            self.obj = obj
            self.subgoals = {subgoals}
        elif operator in [GoalOperator.AT_START, GoalOperator.AT_END, GoalOperator.OVER_ALL]:
            assert isinstance(subgoals, Goal)
            self.subgoals = {subgoals}

    def recursive_atoms(self):
        if self.atom:
            yield self.atom
        for goal in self.subgoals or []:
            for atom in goal.recursive_atoms():
                yield atom

    def __repr_(self):
        if self.atom:
            return str(self.atom)
        elif self.operator in [GoalOperator.EXISTS, GoalOperator.FORALL]:
            return "({op} ({var}) {goals})".format(op=self.operator, var=self.obj, goals=list2str(self.subgoals))
        else:
            return "({op} {goals})".format(op=self.operator, goals=list2str(self.subgoals))

    def __str__(self):
        return self.__repr_()

    def __eq__(self, other):
        return isinstance(other, Goal) and \
               self.operator == other.operator and self.subgoals == other.subgoals and self.obj == other.obj


class EffectOperator(Enum):
    AND = "and"
    NOT = "not"
    WHEN = "when"
    FORALL = "forall"
    AT_START = "at start"
    AT_END = "at end"


class Effect(object):
    atom = None
    operator = None
    subeffects = None
    obj = None
    goal = None

    def __init__(self, operator=None, subeffects=None, atom=None, obj=None, goal=None):
        self.operator = operator
        if operator is None:
            assert isinstance(atom, Atom)
            self.atom = atom
        elif operator == EffectOperator.AND:
            assert all(isinstance(effect, Effect) for effect in subeffects)
            self.subeffects = tuple(subeffects)
        elif operator == EffectOperator.NOT:
            assert isinstance(subeffects, Effect)
            self.subeffects = (subeffects,)
        elif operator == EffectOperator.WHEN:
            assert isinstance(goal, Goal) and isinstance(subeffects, Effect)
            self.goal = goal
            self.subeffects = (subeffects,)
        elif operator == EffectOperator.FORALL:
            assert isinstance(obj, Obj) and isinstance(subeffects, Effect)
            self.obj = obj
            self.subeffects = (subeffects,)
        elif operator in [EffectOperator.AT_START, EffectOperator.AT_END]:
            assert isinstance(subeffects, Effect)
            self.subeffects = (subeffects,)

    def recursive_atoms(self):
        if self.atom:
            yield self.atom
        for effect in self.subeffects or []:
            for atom in effect.recursive_atoms():
                yield atom
        if self.goal:
            for atom in self.goal.recursive_atoms():
                yield atom

    def __repr_(self):
        if self.operator is None:
            return str(self.atom)
        elif self.operator == EffectOperator.FORALL:
            return "({op} ({var}) {effects})".format(op=self.operator, var=self.obj, effects=list2str(self.subeffects))
        elif self.operator == EffectOperator.WHEN:
            return "({op} {goal} {effects})".format(op=self.operator, goal=self.goal, effects=list2str(self.subeffects))
        else:
            return "({op} {effects})".format(op=self.operator, effects=list2str(self.subeffects))

    def __str__(self):
        return self.__repr_()

    def __eq__(self, other):
        return isinstance(other, Effect) and \
               self.atom == other.atom and self.operator == other.operator and \
               self.subeffects == other.subeffects and self.obj == other.obj and self.goal is other.goal


class DurationOperator(Enum):
    AND = "and"
    AT_START = "at start"
    AT_END = "at end"
    SE = "<= ?duration"
    GE = ">= ?duration"
    EQ = "= ?duration"


class Duration(object):
    operator = None
    subdurations = None
    value = None

    def __init__(self, operator=None, subdurations=None, value=None):
        self.operator = operator
        if operator == DurationOperator.AND:
            assert hasattr(subdurations, "__iter__") and all(
                isinstance(duration, Duration) for duration in subdurations)
            self.subdurations = set(subdurations)
        elif operator in [DurationOperator.SE, DurationOperator.GE, DurationOperator.EQ]:
            assert value is not None
            self.value = value
        elif operator in [DurationOperator.AT_START, DurationOperator.AT_END]:
            assert isinstance(subdurations, Duration)
            self.subdurations = {subdurations}

    def __repr_(self):
        if self.operator is None:
            return "()"
        elif self.operator in [DurationOperator.SE, DurationOperator.GE, DurationOperator.EQ]:
            return "({op} {value})".format(op=self.operator, value=self.value)
        else:
            return "({op} {durations})".format(op=self.operator, durations=list2str(self.subdurations))

    def __str__(self):
        return self.__repr_()


class Operator(Scope):
    """Represents an operation. Can be grounded or ungrounded.
    Ungrounded operators have a '?' in names (unbound variables).
    Attributes:

        operator_name -- the name of operator (action in the domain.)
        variable_list -- a dictionary of key-value pairs where the key
                         is the variable name (with the '?') and the
                         value is the value of it when the operator is
                         grounded.
        effect -- a possibly nested Effect
    """
    def __init__(self, name):
        super(Operator, self).__init__()
        self.operator_name = name
        self.variable_list = {}
        self.effect = None

    def effects_and_conditions(self):
        if self.effect:
            return [self.effect]
        return []


class Action(Operator):
    """Represents an action. Can be grounded or ungrounded.
    Ungrounded operators have a '?' in names (unbound variables).
    Attributes:

        precondition -- a possiby nested Goal
        condition -- a possiby nested Goal
    """
    def __init__(self, name):
        super(Action, self).__init__(name)
        self.precondition = None

    def effects_and_conditions(self):
        conditions = [self.precondition] if self.precondition else []
        return super(Action, self).effects_and_conditions() + conditions


class DurativeAction(Operator):
    """Represents an durative-action:

        duration -- a possibly nested Duration
        condition -- a possibly nested Goal
    """
    def __init__(self, name):
        super(DurativeAction, self).__init__(name)
        self.duration = None
        self.condition = None

    def effects_and_conditions(self):
        conditions = [self.condition] if self.condition else []
        return super(DurativeAction, self).effects_and_conditions() + conditions


class DomainListener(pddlListener):
    def __init__(self):
        self.typesdef = False
        self.objects = {}
        self.operators = {}
        self.scopes = []

    def enterActionDef(self, ctx):
        opname = ctx.actionSymbol().getText()
        self.scopes.append(Action(opname))

    def exitActionDef(self, ctx):
        action = self.scopes.pop()
        self.operators[action.operator_name] = action

    def enterDurativeActionDef(self, ctx):
        opname = ctx.actionSymbol().getText()
        self.scopes.append(DurativeAction(opname))

    def exitDurativeActionDef(self, ctx):
        durative_action = self.scopes.pop()
        self.operators[durative_action.operator_name] = durative_action

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
        if hasattr(self.scopes[-1], "variable_list"): # :parameter section, parent scope is of type Operator
            variable_list = self.scopes[-1].variable_list
        else:
            o = Obj()
            variable_list = o.variable_list
            self.scopes[-1].add_by_type(o)
        for v in ctx.VARIABLE():
            vname = v.getText()
            variable_list[v.getText()] = None
        for vs in ctx.singleTypeVarList():
            t = vs.r_type().getText()
            for v in vs.VARIABLE():
                vname = v.getText()
                variable_list[vname] = t

    def enterAtomicTermFormula(self, ctx):
        scope = self.scopes[-1]
        scope.add_by_type(Atom(ctx))

    def enterPrecondition(self, ctx):
        self.scopes.append(Scope())

    def exitPrecondition(self, ctx):
        scope = self.scopes.pop()
        goals = scope.pop(Goal, [])
        operator = self.scopes[-1]
        operator.precondition = goals[0] if goals else None

    def _enterEffect(self, ctx):
        self.scopes.append(Scope())

    def _exitEffect(self, ctx):
        scope = self.scopes.pop()
        if isinstance(ctx.children[0], pddlParser.AtomicTermFormulaContext):
            effect = Effect(atom=scope.pop(Atom)[0])
        elif isinstance(ctx.children[0], pddlParser.TimedEffectContext):
            effect = scope[Effect][0]
        else:
            operator = get_operator(ctx, EffectOperator)
            if operator == EffectOperator.AND:
                effect = Effect(operator, scope.pop(Effect, []))
            elif operator == EffectOperator.NOT:
                atoms = scope.pop(Atom)
                if atoms:
                    effect = Effect(operator, Effect(atom=atoms[0]))
                else:
                    effect = scope.pop(Effect)[0]
            elif operator == EffectOperator.WHEN:
                effect = Effect(operator, scope.pop(Effect)[0], goal=scope.pop(Goal)[0])
            elif operator == EffectOperator.FORALL:
                effect = Effect(operator, scope.pop(Effect)[0], obj=scope.pop(Obj)[0])
            elif operator in [EffectOperator.AT_START, EffectOperator.AT_END]:
                effect = Effect(operator, scope.pop(Effect)[0])
            else:
                raise AttributeError("Unsupported effect operand: {}".format(operator))
        self.scopes[-1].add_by_type(effect)

    def enterEffect(self, ctx):
        self._enterEffect(ctx)

    def exitEffect(self, ctx):
        self._exitEffect(ctx)

    def enterDaEffect(self, ctx):
        self._enterEffect(ctx)

    def exitDaEffect(self, ctx):
        self._exitEffect(ctx)

    def enterTimedEffect(self, ctx):
        self._enterEffect(ctx)

    def exitTimedEffect(self, ctx):
        self._exitEffect(ctx)

    def enterPEffect(self, ctx):
        self._enterEffect(ctx)

    def exitPEffect(self, ctx):
        self._exitEffect(ctx)

    def _enterGoalDesc(self, ctx):
        self.scopes.append(Scope())

    def _exitGoalDesc(self, ctx):
        scope = self.scopes.pop()
        if isinstance(ctx.children[0], pddlParser.AtomicTermFormulaContext):
            goal = Goal(atom=scope.pop(Atom)[0])
        elif isinstance(ctx.children[0], pddlParser.PrefTimedGDContext):
            goal = scope.pop(Goal)[0]
        else:
            operator = get_operator(ctx, GoalOperator)
            if operator in [GoalOperator.AND, GoalOperator.OR, GoalOperator.IMPLY]:
                goal = Goal(operator, scope[Goal])
            elif operator == GoalOperator.NOT:
                goal = Goal(operator, scope.pop(Goal)[0])
            elif operator in [GoalOperator.FORALL, GoalOperator.EXISTS]:
                goal = Goal(operator, scope.pop(Goal)[0], obj=scope.pop(Obj)[0])
            elif operator in [GoalOperator.AT_START, GoalOperator.AT_END, GoalOperator.OVER_ALL]:
                goal = Goal(operator, scope.pop(Goal)[0])
            else:
                raise AttributeError("Unsupported goal operand")
        self.scopes[-1].add_by_type(goal)

    def enterGoalDesc(self, ctx):
        self._enterGoalDesc(ctx)

    def exitGoalDesc(self, ctx):
        self._exitGoalDesc(ctx)

    def enterDaGD(self, ctx):
        self._enterGoalDesc(ctx)

    def exitDaGD(self, ctx):
        self._exitGoalDesc(ctx)

    def enterTimedGD(self, ctx):
        self._enterGoalDesc(ctx)

    def exitTimedGD(self, ctx):
        self._exitGoalDesc(ctx)

    def _enterDurationConstraint(self, ctx):
        self.scopes.append(Scope())

    def _exitDurationConstraint(self, ctx):
        scope = self.scopes.pop()
        operator = get_operator(ctx, DurationOperator)
        if operator is None:
            if not scope[Duration]:
                return
            duration = scope[Duration][0]
        elif operator == DurationOperator.AND:
            duration = Duration(operator, scope[Duration])
        elif operator in [DurationOperator.AT_START, DurationOperator.AT_END]:
            duration = Duration(operator, scope.pop(Duration)[0])
        elif operator in [DurationOperator.SE, DurationOperator.GE, DurationOperator.EQ]:
            value = ctx.children[-2].getText()
            duration = Duration(operator, value=value)
        else:
            raise AttributeError("Unsupported duration operand")
        self.scopes[-1].add_by_type(duration)

    def enterDurationConstraint(self, ctx):
        self._enterDurationConstraint(ctx)

    def exitDurationConstraint(self, ctx):
        self._exitDurationConstraint(ctx)

    def enterSimpleDurationConstraint(self, ctx):
        self._enterDurationConstraint(ctx)

    def exitSimpleDurationConstraint(self, ctx):
        self._exitDurationConstraint(ctx)

    def enterTypedNameList(self, ctx):
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

    def exitActionDefBody(self, ctx):
        operator = self.scopes[-1]
        effects = operator.pop(Effect, [])
        operator.effect = effects[0] if effects else None

    def exitDaDefBody(self, ctx):
        operator = self.scopes[-1]
        duration = operator.pop(Duration, [])
        operator.duration = duration[0] if duration else None
        condition = operator.pop(Goal, [])
        operator.condition = condition[0] if condition else None
        effects = operator.pop(Effect, [])
        operator.effect = effects[0] if effects else None

    def exitDomain(self, ctx):
        if not self.objects and not self.typesdef:
            vs = set()
            for opn, oper in self.operators.items():
                for item in oper.effects_and_conditions():
                    for atom in item.recursive_atoms():
                        for var in atom.variables:
                            vs.add( (var, None) )
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
        scope = self.scopes[-1]
        scope.add_by_type(Atom(ctx))

    def enterAtomicTermFormula(self, ctx):
        scope = self.scopes[-1]
        scope.add_by_type(Atom(ctx))

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

