
# pddlpy README #


This is a PDDL parser library using an ANTLR 4 grammar that provides a very simple interface to interact with domain-problems.
This library publishes one object class whose API exposes methods for obtaining:

* The initial state.
* The goals.
* The list of operators.
* The positive and negative preconditions and the positive and negative effects.
* The _grounded_ states of a given operator (grounded variables, preconditions and effects).

This is enough for the user to focus on the implementation of state-space or plan-space search algorithms.

The development of this tool was inspired from Univerty of Edimburgh's Artificial Intelligence Planning course by Dr. Gerhard Wickler and Prof. Austin Tate. The terms used in this API (and the API itself) closely resembles the ones proposed by the lecturers.

As of today it only supports Python but I plan to give support to .NET and Java languages.

The orginal grammar file was authored by Zeyn Saigol from University of Birmingham. I cleaned up it, made it language agnostic and upgraded to ANTLR 4.


### Who do I talk to? ###

You may contact me directly to hfoffani at gmail.com


