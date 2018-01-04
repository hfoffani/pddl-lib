
ANTLRDIR=/usr/local/opt/antlr
ANTLRLIB=$(ANTLRDIR)/antlr-4.7-complete.jar
ANTLR=$(ANTLRDIR)/bin/antlr4
GRUN=$(ANTLRDIR)/bin/grun

# For dotnet
NUNITVERSION=3.6.1
ANTLRNET=Antlr4.Runtime.Standard
ANTLRDLL=Antlr4.Runtime.Standard.4.7.0/lib/net35/Antlr4.Runtime.Standard.dll
DLLSPATH=../pddlnet
CSANTLR=pddlListener.cs pddlBaseListener.cs pddlLexer.cs pddlParser.cs
NUNITLIB=NUnit.$(NUNITVERSION)/lib/net45/nunit.framework.dll
NUNITLITE=NUnitLite.$(NUNITVERSION)/lib/net45/nunitlite.dll
LIBSTEST=-reference:output/$(NUNITLIB),output/$(NUNITLITE),Microsoft.CSharp,pddlnet
MONOBIN=/Library/Frameworks/Mono.framework/Commands
NUGET=$(MONOBIN)/nuget

pyversion ?= 3
ifeq ($(pyversion),3)
PIP=pip
PYTHON=python
ANTLRLANG=-Dlanguage=Python3
else
PIP=pip
PYTHON=python
ANTLRLANG=-Dlanguage=Python2 -encoding utf8
endif

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
	$(ANTLR) $(ANTLRLANG) -o pddlpy pddl.g4

pytest: pyparser pddlpy/pddl.py
	$(PYTHON) -m pddlpy.test

pydist: pytest
	$(PYTHON) setup.py bdist_wheel
	$(PIP) install -e .

pypitest: pydist
	$(PYTHON) setup.py register -r pypitest && \
	$(PYTHON) setup.py bdist_wheel upload -r pypitest

pypipublish: pydist
	$(PYTHON) setup.py register -r pypi && \
	$(PYTHON) setup.py bdist_wheel upload -r pypi

pydemo: pydist
	cd examples-python && \
	$(PYTHON) demo.py 1 && \
	$(PYTHON) demo.py 2 && \
	$(PYTHON) demo.py 3

csparser: pddl.g4 pddlnet/pddl.cs
	mkdir -p pddlnet && \
	$(ANTLR) -Dlanguage=CSharp -package PDDLNET -o pddlnet pddl.g4 && \
	(cd pddlnet && \
	$(NUGET) install $(ANTLRNET) && \
	$(MONOBIN)/mcs -out:pddlnet.dll -reference:$(ANTLRDLL) -t:library pddl.cs $(CSANTLR))

cstest: csparser pddlnet/pddltest.cs
	(cd pddlnet && \
	mkdir -p output && \
	$(NUGET) install NUnitLite -Verbosity quiet -OutputDirectory output && \
	$(MONOBIN)/mcs -d:NUNIT $(LIBSTEST) -out:output/pddlnettest.exe -reference:$(ANTLRDLL) -t:exe pddltest.cs && \
	cp pddlnet.dll $(ANTLRDLL) output/$(NUNITLIB) output/$(NUNITLITE) output && \
	cd output && \
	$(MONOBIN)/mono pddlnettest.exe )

csnuget: cstest
	(cd pddlnet && \
	rm -f pddlnet.dll.*.nupkg && \
	$(NUGET) pack pddlnet.dll.nuspec )

csnugetpublish: csnuget
	(cd pddlnet && \
	$(NUGET) push pddlnet.dll.*.nupkg )

