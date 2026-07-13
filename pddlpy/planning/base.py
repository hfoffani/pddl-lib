"""Planner interface, capability negotiation and :requirements enforcement.

The public contract is ``Planner.solve(domainproblem) -> Plan | None``.
``DomainProblem`` is the parsed, validated Phase 0 object combining domain
and problem.

Two guards run before search (fail fast, PRD §7):

* **#9 — requirements enforcement**: features the domain actually uses
  (typing, negative preconditions, disjunctive preconditions) must be
  declared in its ``:requirements``.
* **Capability negotiation**: every declared requirement must be in the
  planner's ``capabilities``; otherwise the planner refuses the task.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, FrozenSet, Optional, Set

from .grounding import GroundedTask

if TYPE_CHECKING:
    from pddlpy.pddl import DomainProblem

    from .state import Plan


class PlannerError(Exception):
    """Base class for planner-layer errors."""


class UnsupportedRequirementsError(PlannerError):
    """Raised when a domain's features/requirements are not supported."""


# Map a detectable feature to the requirement keywords that permit it.
# ':adl' is the umbrella requirement implying the full ADL feature set.
_FEATURE_REQUIREMENTS: Dict[str, Set[str]] = {
    "typing": {":typing", ":adl"},
    "negative-preconditions": {":negative-preconditions", ":adl"},
    "disjunctive-preconditions": {":disjunctive-preconditions", ":adl"},
    "equality": {":equality", ":adl"},
    "existential-preconditions":
        {":existential-preconditions", ":quantified-preconditions", ":adl"},
    "universal-preconditions":
        {":universal-preconditions", ":quantified-preconditions", ":adl"},
    "conditional-effects": {":conditional-effects", ":adl"},
}


def _used_features(domainproblem: "DomainProblem") -> Set[str]:
    """Detect which (enforceable) PDDL features a domain actually uses.

    Beyond typing, the ADL features (#10) are read off the operators'
    precondition and effect trees: negation, disjunction, equality,
    quantifiers, and conditional/universal effects.
    """
    features: Set[str] = set()
    if domainproblem.domain.typesdef or any(
        t is not None for t in domainproblem.worldobjects().values()
    ):
        features.add("typing")
    for op in domainproblem.domain.operators.values():
        if op.precondition_tree is not None:
            features |= op.precondition_tree.features()
        if op.effect_tree is not None:
            features |= op.effect_tree.features()
    return features


def validate_requirements(domainproblem: "DomainProblem") -> None:
    """#9: ensure used features are declared in ``:requirements``.

    Only enforced when the domain declares at least one requirement (i.e. it
    has opted into the requirements system); fully requirement-free files are
    left lenient, matching common real-world usage.
    """
    declared = domainproblem.requirements()
    if not declared:
        return
    for feature in _used_features(domainproblem):
        if not (_FEATURE_REQUIREMENTS[feature] & declared):
            raise UnsupportedRequirementsError(
                "domain uses %s but does not declare a matching requirement "
                "(one of %s)"
                % (feature, sorted(_FEATURE_REQUIREMENTS[feature]))
            )


class Planner(ABC):
    """Abstract solver. Subclasses declare ``capabilities`` and implement
    ``solve``.

    ``capabilities`` is the set of ``:requirements`` keywords the planner can
    handle. ``prepare`` enforces requirements + capabilities and returns a
    ``GroundedTask`` ready for search.
    """

    #: requirement keywords this planner supports
    capabilities: FrozenSet[str] = frozenset()

    def check_capabilities(self, domainproblem: "DomainProblem") -> None:
        """Raise if the domain declares a requirement beyond this planner's
        capabilities."""
        unsupported = domainproblem.requirements() - set(self.capabilities)
        if unsupported:
            raise UnsupportedRequirementsError(
                "%s does not support %s"
                % (type(self).__name__, sorted(unsupported))
            )

    def prepare(self, domainproblem: "DomainProblem") -> GroundedTask:
        """Run #9 + capability checks, then build the GroundedTask."""
        validate_requirements(domainproblem)
        self.check_capabilities(domainproblem)
        return GroundedTask(domainproblem)

    @abstractmethod
    def solve(self, domainproblem: "DomainProblem") -> "Optional[Plan]":
        """Return a ``Plan`` reaching the goal, or ``None`` if none exists."""
        raise NotImplementedError  # pragma: no cover - abstract
