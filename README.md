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

There are two ways to use this project.


`pip install antlr4-python3-runtime`

* Configuration
* Dependencies
* Database configuration
* How to run tests
* Deployment instructions

### Things to do ###

* This README.
* Copyrights.
* API description.
* AI Plan jargon.
* Demo program.
* Tests.
* PIP package.
* C# version.
* NuGet package.
* Java version.
* Java Central Repository.


### Contribution guidelines ###

I'd appreciate any feedback you send like pull requests, bug reports, etc.


### Who do I talk to? ###

Emailme at 

