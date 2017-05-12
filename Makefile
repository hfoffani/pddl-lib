
ANTLRDIR=/usr/local/opt/antlr
ANTLRLIB=$(ANTLRDIR)/antlr-4.6-complete.jar
ANTLR=$(ANTLRDIR)/bin/antlr4
GRUN=$(ANTLRDIR)/bin/grun
ANTLRNET=Antlr.4.Runtime
ANTLRREF=-reference:Antlr.4.Runtime.4.6.0/lib/net35/Antlr4.Runtime.dll
DLLSPATH=../pddlnet
CSANTLR=pddlListener.cs pddlBaseListener.cs pddlLexer.cs pddlParser.cs
LIBSTEST=-reference:NUnit.Framework,Microsoft.CSharp,pddlnet
MONOPATH=/Library/Frameworks/Mono.framework/Libraries/mono/4.5/
NUNITCONSOLE="/Library/Frameworks/Mono.framework/Versions/Current/bin/nunit-console4"
MONOBIN=/Library/Frameworks/Mono.framework/Commands
NUGET=$(MONOBIN)/nuget

pyversion ?= 3
ifeq ($(pyversion),3)
PIP=pip3
PYTHON=python3
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

pydist: pyparser pddlpy/pddl.py
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
	$(MONOBIN)/mcs -out:pddlnet.dll $(ANTLRREF) -t:library pddl.cs $(CSANTLR))

cstest: csparser pddlnet/pddltest.cs
	(cd pddlnet && \
	$(MONOBIN)/mcs -d:NUNIT $(LIBSTEST) -out:pddlnettest.dll $(ANTLRREF) -t:library pddltest.cs && \
	MONO_PATH=$(MONOPATH) $(NUNITCONSOLE) pddlnettest.dll --nologo )

csnuget: csparser
	(cd pddlnet && \
	rm -f pddlnet.dll.*.nupkg && \
	$(NUGET) pack pddlnet.dll.nuspec )

csnugetpublish: csnuget
	(cd pddlnet && \
	$(NUGET) push pddlnet.dll.*.nupkg )


binrelease: cstest
	(cd pddlnet && \
	zip pddlnetdll.zip pddlnet.dll $(ANTLRNET) )


