# README #


### What is this repository for? ###

This is a PDDL parser library using an ANTLR 4 grammar that provides a very simple interface to interact with domain-problems.
This library publishes one object class whose API exposes methods for obtaining:
* The initial state.
* The goals.
* The list of operators.
* The positive and negative preconditions and the positive and negative effects.
* The /grounded/ states of a given operator (grounded variables, preconditions and effects).

This is enough for the user to focus on the implementation of state-space or plan-space search algorithms.

As of today it only supports Python but I plan to give support to .NET and Java languages.

The orginal grammar file was authored by XXX. I cleaned up it, made it language agnostic and upgraded to ANTLR 4.


### What this project is NOT? ###

This library doesn't include and won't include algorithms for solutions search.
There are lots of projects and complete packages for planning available. This project is just a library that provides the user a simple PDDL helper API useful when she experiments with her own planning algorithms.

### How do I get set up? ###


#### Prerequisites

* Install ANTLR version 4.
    I used `brew install antlr4` (a Mac). Your mileage may vary depending on your environment.
* Install Python 3.
    For this I also used brew.
* Install antlr4 runtime.
    `pip install antlr4-python3-runtime`

#### Building

* Checkout the repository.
* Edit the Makefile to configure PATHs.
* Run `make` 

#### Running a program.

The file `demo.py` shows how to use this library.


### Things to do ###

* Copyrights.
* API description.
* AI Plan jargon.
* Demo program.


### Known bugs ###

* The library expands the variables (ground them) using a cartesian product of the domains of each variable.
    It should consider only the ones /admissible/ for a given state.

### Future development ###


* More tests
* Publish the Python library as a PIP package.
* C# version.
* Publish the .NET library as a NuGet package.
* Java version.
* Publish the Java library in the Java Central Repository.


### Contribution guidelines ###

I'd appreciate any feedback you send like pull requests, bug reports, etc.


### Who do I talk to? ###

Emailme at 

