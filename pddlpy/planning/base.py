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
from abc import ABC, abstractmethod

from .grounding import GroundedTask


class PlannerError(Exception):
    """Base class for planner-layer errors."""


class UnsupportedRequirementsError(PlannerError):
    """Raised when a domain's features/requirements are not supported."""


# Map a detectable feature to the requirement keywords that permit it.
# ':adl' is the umbrella requirement implying typing + negative + disjunctive.
_FEATURE_REQUIREMENTS = {
    "typing": {":typing", ":adl"},
    "negative-preconditions": {":negative-preconditions", ":adl"},
    "disjunctive-preconditions": {":disjunctive-preconditions", ":adl"},
}


def _used_features(domainproblem):
    """Detect which (enforceable) PDDL features a domain actually uses."""
    features = set()
    if domainproblem.domain.typesdef or any(
        t is not None for t in domainproblem.worldobjects().values()
    ):
        features.add("typing")
    for op in domainproblem.domain.operators.values():
        if op.precondition_neg:
            features.add("negative-preconditions")
        if op.precondition_connective == "or":
            features.add("disjunctive-preconditions")
    return features


def validate_requirements(domainproblem):
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
    capabilities = frozenset()

    def check_capabilities(self, domainproblem):
        """Raise if the domain declares a requirement beyond this planner's
        capabilities."""
        unsupported = domainproblem.requirements() - set(self.capabilities)
        if unsupported:
            raise UnsupportedRequirementsError(
                "%s does not support %s"
                % (type(self).__name__, sorted(unsupported))
            )

    def prepare(self, domainproblem):
        """Run #9 + capability checks, then build the GroundedTask."""
        validate_requirements(domainproblem)
        self.check_capabilities(domainproblem)
        return GroundedTask(domainproblem)

    @abstractmethod
    def solve(self, domainproblem):
        """Return a ``Plan`` reaching the goal, or ``None`` if none exists."""
        raise NotImplementedError
