
## pddl-lib ##

### Description ###

A PDDL library that, by using an ANTLR 4 grammar to parse PDDL files, provides a very simple interface to interact with domain-problems.
This library publishes one object class whose API exposes methods for obtaining:

* The initial state.
* The goals.
* The list of operators.
* The positive and negative preconditions and the positive and negative effects.
* The _grounded_ states of a given operator (grounded variables, preconditions and effects).

This is enough for the user to focus on the implementation of state-space or plan-space search algorithms.

The development of this tool was inspired from Univerty of Edinburgh's Artificial Intelligence Planning course by Dr. Gerhard Wickler and Prof. Austin Tate. The terms used in this API (and the API itself) closely resembles the ones proposed by the lecturers.

As of today it supports Python 3.8 and up.

The orginal grammar file was authored by Zeyn Saigol from University of Birmingham. I cleaned up it, made it language agnostic and upgraded to ANTLR 4.


### NOTICE ###

Currently the main branch is broken. I will be publishing to PyPI from this branch. While the parser does recognize durations you cannot recover these tags from Python.


### What this project is not? ###

This library doesn't include and won't include algorithms for solutions search.
There are lots of projects and complete packages for planning available. This project is just a library that provides the user a simple PDDL helper API useful when she experiments with her own planning algorithms.


### Examples ###

In this repostory you'll find some PDDL examples files useful for testing purposes.
For instance, [domain-03.pddl](examples-pddl/domain-03.pddl)
and [problem-03.pddl](examples-pddl/problem-03.pddl)


### Using the PDDL Python library ###

To use this library the recommended way is to install it via PIP:
```
pip install pddlpy
```

It would download `pddlpy` and its dependencies (`antlr4-python3-runtime`) from PYPI and install them.
And that's it. You are ready to go.

Using the library is easy.

```
~hernan$ python
Python 3.8.0 (default, Nov 20 2019, 14:40:03) 
[Clang 11.0.0 (clang-1100.0.33.12)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>
>>> import pddlpy
>>> domprob = pddlpy.DomainProblem('domain-03.pddl', 'problem-03.pddl')
>>>

>>> domprob.initialstate()
{('unloaded', 'robr'), ('adjacent', 'loc2', 'loc1'), ('unloaded', 'robq'), ('in', 'conta', 'loc1'), ('in', 'contb', 'loc2'), ('atl', 'robr', 'loc1'), ('atl', 'robq', 'loc2'), ('adjacent', 'loc1', 'loc2')}
>>>

>>> list( domprob.operators() )
['move', 'load', 'unload']
>>>

>>> list( domprob.ground_operator('move') )
[<pddlpy.pddl.Operator object at 0x1089830a0>, <pddlpy.pddl.Operator object at 0x108983130>, <pddlpy.pddl.Operator object at 0x108983190>, <pddlpy.pddl.Operator object at 0x1089830d0>, <pddlpy.pddl.Operator object at 0x1089831c0>, <pddlpy.pddl.Operator object at 0x1089835b0>, <pddlpy.pddl.Operator object at 0x1089835e0>, <pddlpy.pddl.Operator object at 0x108983610>]
>>>

>>> list( domprob.ground_operator('move') )[0].precondition_pos
{('atl', 'robq', 'loc2'), ('adjacent', 'loc2', 'loc2')}
>>>
```
The pddl files are examples obtained from the course material.


### Other Resources ###

There are wonderful material at the the University of Edinburgh:
* [AI Planning MOOC Project Home Page](http://www.aiai.ed.ac.uk/project/plan/ooc)
* [Index to access all course materials and videos](http://media.aiai.ed.ac.uk/Project/AIPLAN)
* [Videos on YouTube](http://bit.ly/aiplanmooc)



### Future development ###

* Implement the `:requirements` directive.
* Add more examples (time durataion, a simple planner maybe?).
* Add API documentation.
* More unit tests.


### Adavanced ###

In case you want to tweak the grammar, add other target languages or modify the library you will need build this project from the repository sources.

#### Prerequisites

* Install ANTLR version 4.
    I used `brew install antlr4` (a Mac). Your mileage may vary depending on your environment.
* Install Python 3
    For this I also used brew.
* Install antlr4 runtime.
    `pip install antlr4-python3-runtime`
* The package is built using wheel.
    `pip install wheel`

#### Building

* Checkout the repository.
* Edit the Makefile to configure PATHs.
* Run `make` (it includes tests.)


### Contribution guidelines ###

I'd appreciate any feedback you send like pull requests, bug reports, etc.

Please, use the issue tracker at will.


### Acknowledgments

Michiaki Tatsubori [@tatsubori](https://github.com/tatsubori) added time-duration support. Thanks!


### License ###

This project is publish under the
[Apache License](http://www.apache.org/licenses/LICENSE-2.0).


### Who do I talk to? ###

For questions or requests post an issue here or tweet me at
[@herchu](http://twitter.com/herchu)



