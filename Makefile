
ANTLR=/usr/local/Cellar/antlr/4.5/bin/antlr4

all: pddl.g4
	$(ANTLR) -Dlanguage=Python3 -o parser pddl.g4

