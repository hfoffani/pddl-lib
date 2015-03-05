# README #


### Description ###

This is a PDDL parser library using an ANTLR 4 grammar that provides a very simple interface to interact with domain-problems.
This library publishes one object class whose API exposes methods for obtaining:

* The initial state.
* The goals.
* The list of operators.
* The positive and negative preconditions and the positive and negative effects.
* The _grounded_ states of a given operator (grounded variables, preconditions and effects).

This is enough for the user to focus on the implementation of state-space or plan-space search algorithms.

The development of this tool was inspired from Univerty of Edimburgh's Artificial Intelligence Planning course by Dr. Gerhard Wickler and Prof. Austin Tate. The terms used in this API (and the API itself) closely resembles the ones proposed by the lecturers.

As of today it only supports Python 3 but I plan to give support to .NET and Java languages.

The orginal grammar file was authored by Zeyn Saigol from University of Birmingham. I cleaned up it, made it language agnostic and upgraded to ANTLR 4.


### What this project is not? ###

This library doesn't include and won't include algorithms for solutions search.
There are lots of projects and complete packages for planning available. This project is just a library that provides the user a simple PDDL helper API useful when she experiments with her own planning algorithms.


### Using the library ###

To use this library the recommended way is to install it via PIP:
```
pip install pddlpy
```

It would download `pddlpy` and its dependencies (`antlr4-python3-runtime`) from PYPI and install them.
And that's it. You are ready to go.

The next step is to pick up some of the demos available here to learn how to use the library.

```
python demo.py { 1|2|3 }
```
The pddl files are examples obtained from the course material.

Analyse the file `demo.py` to understand the API.


### Future development ###

* Publish API documentations and examples.
* C# version.
* Publish the .NET library as a NuGet package.
* Unit tests.
* Java version.
* Publish the Java library in the Java Central Repository.
* The process that grounds variables is very simple (it's a cartesian product) and needs to be optimized.


### Adavanced ###

In case you want to tweak the grammar, add other target languages or modify the library you will need build this project from the repository sources.

#### Prerequisites

* Python 3
* Install ANTLR version 4.
    I used `brew install antlr4` (a Mac). Your mileage may vary depending on your environment.
* Install Python 3.
    For this I also used brew.
* Install antlr4 runtime.
    `pip install antlr4-python3-runtime`
* To publish the package you'll also need:
    `pip install wheel`
    `pip install tween`

#### Building

* Checkout the repository.
* Edit the Makefile to configure PATHs.
* Run `make` (it includes tests.)


### Contribution guidelines ###

I'd appreciate any feedback you send like pull requests, bug reports, etc.

Please, use the issue tracker at will.


### License ###

This project is publish under the MIT Open Source license.


### Who do I talk to? ###

You may contact me directly to hfoffani at gmail.com


