

ANTLRDIR=/usr/local/Cellar/antlr/4.12.0
ANTLRLIB=$(ANTLRDIR)/antlr-4.12.0-complete.jar
ANTLR=$(ANTLRDIR)/bin/antlr
GRUN=$(ANTLRDIR)/bin/grun


ANTLRLANG=-Dlanguage=Python3
PYTHON=python
PIP=pip

export CLASSPATH:=.:$(ANTLRLIB)

all: testgrammar pytest


testgrammar: pddl.g4
	mkdir -p tmp && \
	$(ANTLR) -o tmp pddl.g4 && \
	cd tmp && javac *.java && \
	$(GRUN) pddl domain ../examples-pddl/domain-01.pddl && \
	$(GRUN) pddl problem ../examples-pddl/problem-01.pddl

pyparser: pddl.g4
	mkdir -p pddlpy && \
	$(ANTLR) $(ANTLRLANG) -o pddlpy pddl.g4

pytest: pyparser pddlpy/pddl.py
	$(PYTHON) -m pddlpy.test

pydist: pytest
	$(PYTHON) setup.py bdist_wheel

pypitest: pydist
	$(PYTHON) -m twine upload --repository testpypi dist/`ls -t dist | head -1`

pypipublish: pydist
	$(PYTHON) -m twine upload dist/`ls -t dist | head -1`

pydemo: pytest
	for i in 1 2 3 4 6; do $(PYTHON) demo.py $$i ; done
