

ANTLRDIR=/usr/local/Cellar/antlr/4.9.3
ANTLRLIB=$(ANTLRDIR)/antlr-4.9.3-complete.jar
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
	$(PYTHON) setup.py sdist bdist_wheel

pypitest: pydist
	echo hello
	# $(PYTHON) setup.py register -r pypitest && \
	# $(PYTHON) setup.py bdist_wheel upload -r pypitest

pypipublish: pydist
	echo hello
	# $(PYTHON) setup.py register -r pypi && \
	# $(PYTHON) setup.py bdist_wheel upload -r pypi

pydemo: pytest
	$(PYTHON) demo.py 1 && \
	$(PYTHON) demo.py 2 && \
	$(PYTHON) demo.py 3

