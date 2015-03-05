
ANTLRDIR=/usr/local/Cellar/antlr/4.5
ANTLRLIB=$(ANTLRDIR)/antlr-4.5-complete.jar
ANTLR=$(ANTLRDIR)/bin/antlr4
GRUN=$(ANTLRDIR)/bin/grun

export CLASSPATH:=.:$(ANTLRLIB)

all: testgrammar parsers

parsers: pyparser csparser

testgrammar: pddl.g4
	mkdir -p tmp && \
	$(ANTLR) -o tmp pddl.g4 && \
	cd tmp && javac *.java && \
	$(GRUN) pddl domain ../examples-pddl/domain-01.pddl && \
	$(GRUN) pddl problem ../examples-pddl/problem-01.pddl


pyparser: pddl.g4
	mkdir -p pddlpy && \
	$(ANTLR) -Dlanguage=Python3 -o pddlpy pddl.g4

pydist:
	python3 setup.py bdist_wheel
	pip3 install -e .

pypitest: pydist
	python setup.py register -r pypitest && \
	python setup.py bdist_wheel upload -r pypitest

pypipublish: pydist
	python setup.py register -r pypi && \
	python setup.py bdist_wheel upload -r pypi

pydemo: pydist
	cd examples-python && \
	python3 demo.py 1 && \
	python3 demo.py 2 && \
	python3 demo.py 3

csparser: pddl.g4
	mkdir -p pddlnet && \
	$(ANTLR) -Dlanguage=CSharp -o pddlnet pddl.g4

