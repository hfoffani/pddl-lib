"""PDDL diagnostics (#94): machine-checkable validation of a domain/problem pair.

Aimed at the agentic NL->PDDL loop: a parse that "succeeds" is not enough,
because ANTLR error-recovers (syntax errors only go to stderr) and a
semantically-off translation typically shows up as atoms over undeclared
predicates, ground atoms naming unknown objects, or operators that ground
to zero instances. :func:`diagnose` bundles those checks into one JSON-able
verdict, shared by ``pddlpy validate`` (CLI, #85) and the ``validate`` MCP
tool (#86).

This module sits at the object-model layer: like ``pddlpy.pddl`` it may
import the generated grammar (the planning layer may not).
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Set, Tuple

from pddlpy._vendor.antlr4 import CommonTokenStream
from pddlpy._vendor.antlr4.error.ErrorListener import ErrorListener
from pddlpy.pddl import DomainProblem, source_stream
from pddlpy.pddlLexer import pddlLexer
from pddlpy.pddlParser import pddlParser
from pddlpy.planning import (
    DurativeValidationError,
    UnsupportedRequirementsError,
    atom_tuple,
    check_modeled,
    validate_durative_actions,
    validate_requirements,
)


class _CollectingErrorListener(ErrorListener):
    """Accumulates ANTLR syntax errors instead of printing them to stderr."""

    def __init__(self) -> None:
        self.errors: List[str] = []

    def syntaxError(self, recognizer: Any, offendingSymbol: Any, line: int,
                    column: int, msg: str, e: Any) -> None:
        self.errors.append("line %d:%d %s" % (line, column, msg))


def _syntax_errors(path: str, rule: str) -> List[str]:
    """Parse ``path`` with the grammar rule ``rule`` ('domain' or 'problem')
    and return the collected syntax errors."""
    collector = _CollectingErrorListener()
    lexer = pddlLexer(source_stream(path))
    lexer.removeErrorListeners()
    lexer.addErrorListener(collector)
    parser = pddlParser(CommonTokenStream(lexer))
    parser.removeErrorListeners()
    parser.addErrorListener(collector)
    getattr(parser, rule)()
    return collector.errors


def _init_atoms(dp: DomainProblem) -> Iterator[Any]:
    """Every atom written in :init, including the ones kept out of the
    initial state: negated (#186) and timed (#142) literals still have to
    name declared predicates and objects."""
    yield from dp.initialstate()
    yield from dp.problem.negative_init
    for _, atom, _ in dp.problem.timed_literals:
        yield atom


def _condition_atoms(dp: DomainProblem) -> Iterator[Tuple[str, Any]]:
    """Yield ``(where, atom)`` for every atom referenced by the model:
    init, goal, and each (durative) action's conditions and effects."""
    for atom in _init_atoms(dp):
        yield ":init", atom
    for atom in dp.goals():
        yield ":goal", atom
    for name, op in dp.domain.operators.items():
        # Walk the ADL precondition/effect trees so atoms nested inside
        # or/forall/exists/when/= are checked too (#10), not just the flat
        # unconditional summary sets.
        if op.precondition_tree is not None:
            for atom in op.precondition_tree.atoms():
                yield "action %r" % name, atom
        if op.effect_tree is not None:
            for atom in op.effect_tree.atoms():
                yield "action %r" % name, atom
    for name, dop in dp.domain.durative_operators.items():
        for timed in (dop.condition_pos, dop.condition_neg):
            for atoms in timed.values():
                for atom in atoms:
                    yield "durative action %r" % name, atom
        for timed in (dop.effect_pos, dop.effect_neg):
            for atoms in timed.values():
                for atom in atoms:
                    yield "durative action %r" % name, atom


def _fmt(atom: Tuple[str, ...]) -> str:
    return "(%s)" % " ".join(atom)


def _issue(severity: str, check: str, message: str) -> Dict[str, str]:
    return {"severity": severity, "check": check, "message": message}


def diagnose(domainfile: str, problemfile: str) -> Dict[str, Any]:
    """Validate a domain/problem pair; returns ``{"valid": bool, "issues": [...]}``.

    Each issue is ``{"severity": "error"|"warning", "check": ..., "message": ...}``.
    ``valid`` is False when any error-severity issue is present (warnings —
    currently only ``zero_groundings`` — leave the pair valid but suspicious).
    On syntax errors the semantic checks are skipped: the recovered model
    would produce misleading follow-on findings.
    """
    issues: List[Dict[str, str]] = []

    for path, rule, which in ((domainfile, "domain", "domain file"),
                              (problemfile, "problem", "problem file")):
        for err in _syntax_errors(path, rule):
            issues.append(_issue("error", "syntax", "%s: %s" % (which, err)))
    if issues:
        return {"valid": False, "issues": issues}

    dp = DomainProblem(domainfile, problemfile)

    # Atoms over predicates the domain never declares.
    declared = dp.predicates()
    if declared:
        seen: Dict[str, Set[str]] = {}
        for where, atom in _condition_atoms(dp):
            pred = atom_tuple(atom)[0]
            if pred not in declared:
                seen.setdefault(pred, set()).add(where)
        for pred in sorted(seen):
            issues.append(_issue(
                "error", "undeclared_predicate",
                "predicate %r is not declared in :predicates (used in %s)"
                % (pred, ", ".join(sorted(seen[pred])))))

    # Ground atoms (init/goal) naming objects that were never declared.
    objects = set(dp.worldobjects())
    unknown: Dict[str, Set[str]] = {}
    for where, atoms in ((":init", _init_atoms(dp)), (":goal", dp.goals())):
        for atom in atoms:
            for term in atom_tuple(atom)[1:]:
                # in a quantified goal (#138) a ?variable is bound, not an
                # object; in a positive conjunction it is free, and an error
                bound = term.startswith("?") and not dp.problem.simple_goal
                if term not in objects and not bound:
                    unknown.setdefault(term, set()).add(where)
    for term in sorted(unknown):
        issues.append(_issue(
            "error", "unknown_object",
            "object %r is not declared in :objects (used in %s)"
            % (term, ", ".join(sorted(unknown[term])))))

    # (not ...) in :init (#186): false anyway (closed world), so ignored; an
    # error when the same atom is also asserted.
    init = {atom_tuple(a) for a in dp.initialstate()}
    for atom in dp.problem.negative_init:
        t = atom_tuple(atom)
        if t in init:
            issues.append(_issue(
                "error", "negative_init",
                "%s is both asserted and negated in :init" % _fmt(t)))
        else:
            issues.append(_issue(
                "warning", "negative_init",
                "(not %s) in :init is ignored: atoms not listed are false" % _fmt(t)))

    # Operators that ground to zero instances: legal, but in an agent-written
    # translation almost always a mistyped object, type, or static predicate.
    for name in sorted(dp.operators()):
        if next(dp.ground_operator(name), None) is None:
            issues.append(_issue(
                "warning", "zero_groundings",
                "operator %r grounds to zero instances" % name))

    # Features used but not declared in :requirements: the check solve runs
    # (#144), so validate never passes a pair that solve then refuses.
    try:
        validate_requirements(dp)
    except UnsupportedRequirementsError as exc:
        issues.append(_issue("error", "requirements", str(exc)))

    # Parts the model reads but drops (#140): solve refuses them too.
    try:
        check_modeled(dp, syntax=False)  # syntax errors are reported above
    except UnsupportedRequirementsError as exc:
        issues.append(_issue("error", "unsupported", str(exc)))

    # Durative structure (duration positive, parameters/predicates declared).
    try:
        validate_durative_actions(dp)
    except DurativeValidationError as exc:
        issues.append(_issue("error", "durative", str(exc)))

    valid = not any(i["severity"] == "error" for i in issues)
    return {"valid": valid, "issues": issues}
