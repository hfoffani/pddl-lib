
ANTLR=/usr/local/Cellar/antlr/4.4/bin/antlr4

all: pddl.g4
	$(ANTLR) -Dlanguage=Python3 pddl.g4

