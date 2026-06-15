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

"""Variable binding strategies for operator grounding (#12).

Grounding an operator means enumerating the value assignments for its
parameters. The historical strategy was a blind cartesian product over each
parameter's type-compatible objects, which does not scale and offered no way
to customise it.

This module factors binding out behind the :class:`VariableBinder` interface so
it can be swapped or overridden:

- :class:`CartesianBinder` reproduces the original full product.
- :class:`StaticPrunedBinder` (the default) prunes assignments that can never be
  applicable by joining the operator's *static* positive preconditions against
  the initial state — sound, because a static predicate (one no action ever
  modifies) has the same truth value in every reachable state as in the initial
  state. It never drops a genuinely applicable grounding.

Binders are stateless and receive the ``DomainProblem`` plus the lifted operator
on each call, so there is no cross-operator caching to get wrong (#26).

A custom binder only needs to implement ``bind(dp, operator)`` and yield
``{param: object}`` dicts; useful ``DomainProblem`` helpers are
``candidate_objects(type)``, ``worldobjects()``, ``initialstate()`` and
``static_predicates()``.
"""
from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from typing import Dict, Iterator, List, Optional


class VariableBinder(ABC):
    """Strategy that enumerates parameter bindings for an operator (#12)."""

    @abstractmethod
    def bind(self, dp, operator) -> Iterator[Dict[str, str]]:
        """Yield ``{param_name: object_name}`` assignments, one per grounding.

        dp        -- the DomainProblem being grounded.
        operator  -- the lifted Operator whose ``variable_list`` maps each
                     parameter to its declared type (or None if untyped).
        """
        raise NotImplementedError  # pragma: no cover - abstract


class CartesianBinder(VariableBinder):
    """Full cartesian product of each parameter over its type-compatible
    objects — the original (subtype-aware, #22) behaviour, with no pruning."""

    def bind(self, dp, operator) -> Iterator[Dict[str, str]]:
        params = list(operator.variable_list.items())
        domains = [dp.candidate_objects(t) for _, t in params]
        names = [name for name, _ in params]
        for combo in itertools.product(*domains):
            yield dict(zip(names, combo))


class StaticPrunedBinder(VariableBinder):
    """Default binder: prune bindings using static preconditions (#12).

    Positive precondition atoms over static predicates are joined against the
    initial state (each variable additionally type-checked), so only bindings
    that satisfy them are generated; the remaining free parameters expand over
    their type domain. Negative static preconditions filter out bindings whose
    atom is present in the initial state. This yields a subset of the cartesian
    bindings, dropping only ones that can never be applicable.
    """

    def bind(self, dp, operator) -> Iterator[Dict[str, str]]:
        # Pruning assumes the positive preconditions must all hold (a
        # conjunction). For a disjunctive precondition (#13) the flattened atoms
        # are alternatives, not conjuncts, so static joining would be unsound —
        # fall back to the full cartesian product.
        if operator.precondition_connective != 'and':
            yield from CartesianBinder().bind(dp, operator)
            return

        static = dp.static_predicates()
        init = {a.ground({}) for a in dp.initialstate()}
        objtype = dp.worldobjects()

        pos = [a for a in operator.precondition_pos if a.predicate[0] in static]
        neg = [a for a in operator.precondition_neg if a.predicate[0] in static]

        # Seed with the empty assignment, then join each static positive atom
        # against matching initial-state tuples.
        partials: List[Dict[str, str]] = [{}]
        for atom in pos:
            pattern = atom.predicate
            name = pattern[0]
            candidates = [t for t in init
                          if t[0] == name and len(t) == len(pattern)]
            nxt: List[Dict[str, str]] = []
            for partial in partials:
                for tup in candidates:
                    merged = self._unify(partial, pattern, tup, operator, dp, objtype)
                    if merged is not None:
                        nxt.append(merged)
            partials = nxt
            if not partials:
                return  # a static positive precondition is unsatisfiable

        names = list(operator.variable_list.keys())
        for partial in partials:
            free = [v for v in names if v not in partial]
            domains = [dp.candidate_objects(operator.variable_list[v]) for v in free]
            for combo in itertools.product(*domains):
                full = dict(partial)
                full.update(zip(free, combo))
                if any(a.ground(full) in init for a in neg):
                    continue  # a static negative precondition is violated
                yield full

    @staticmethod
    def _unify(partial, pattern, tup, operator, dp, objtype) -> Optional[Dict[str, str]]:
        """Extend ``partial`` by matching atom ``pattern`` to init tuple ``tup``.

        Returns the merged assignment, or None on a conflict: a constant
        mismatch, a variable rebound to a different value, or a value whose type
        is not compatible with the parameter's declared type.
        """
        merged = dict(partial)
        for sym, val in zip(pattern[1:], tup[1:]):
            if sym.startswith('?'):
                if not dp._is_subtype(objtype.get(val), operator.variable_list[sym]):
                    return None
                if merged.get(sym, val) != val:
                    return None
                merged[sym] = val
            elif sym != val:
                return None  # constant in the precondition must match
        return merged
