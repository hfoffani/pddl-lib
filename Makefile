

# ANTLR configuration (use 4.9.3 for Java 8 compatibility)
ANTLRVERSION=4.13.2
ANTLRJAR=antlr-$(ANTLRVERSION)-complete.jar
ANTLRURL=https://www.antlr.org/download/$(ANTLRJAR)
ANTLR=java -jar $(ANTLRJAR)
GRUN=java -cp $(ANTLRJAR) org.antlr.v4.gui.TestRig


ANTLRLANG=-Dlanguage=Python3
PYTHON=python
PIP=pip

export CLASSPATH:=.:$(ANTLRJAR)

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
	$(PIP) wheel --no-deps -w dist .

pypitest: pydist
	$(PYTHON) -m twine upload --repository testpypi dist/`ls -t dist | head -1`

pypipublish: pydist
	$(PYTHON) -m twine upload dist/`ls -t dist | head -1`

pydemo: pytest
	for i in 1 2 3 4 6; do $(PYTHON) demo.py $$i ; done
