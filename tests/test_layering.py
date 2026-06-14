"""Strict layer boundaries (PRD acceptance):

* No planner module imports from the ANTLR grammar layer
  (pddlLexer / pddlParser / pddlListener).
* The object model (pddlpy/pddl.py) imports nothing from the planner layer.

Enforced by static import inspection so it cannot be bypassed by indirection
through the model.
"""
import ast
import os

PKG = os.path.join(os.path.dirname(__file__), os.pardir, "pddlpy")
PLANNING = os.path.join(PKG, "planning")

GRAMMAR_MODULES = {"pddlLexer", "pddlParser", "pddlListener"}


def _imported_modules(path):
    """Return the set of top-level/leaf module names imported by a file."""
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[-1])
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names.add(mod)
            names.add(mod.split(".")[-1])
            for alias in node.names:
                names.add(alias.name)
    return names


def _py_files(directory):
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(".py")
    ]


def test_planner_does_not_import_grammar():
    for path in _py_files(PLANNING):
        imported = _imported_modules(path)
        leaked = imported & GRAMMAR_MODULES
        assert not leaked, "%s imports grammar modules %s" % (
            os.path.basename(path),
            leaked,
        )


def test_model_does_not_import_planner():
    imported = _imported_modules(os.path.join(PKG, "pddl.py"))
    assert "planning" not in imported
    assert not any("planning" in name for name in imported)
