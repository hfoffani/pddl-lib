
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

As of today it supports Python 3 and .NET. While project name is `pddl-lib` to emphasize its language agnosticy each target library has its own name. For Python is `pddlpy`. For .NET the library is `pddlnet.dll`.

The orginal grammar file was authored by Zeyn Saigol from University of Birmingham. I cleaned up it, made it language agnostic and upgraded to ANTLR 4.



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
Python 3.4.3 (default, Feb 25 2015, 21:28:45) 
[GCC 4.2.1 Compatible Apple LLVM 6.0 (clang-600.0.56)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>> 
>>> import pddlpy
>>> domprob = pddlpy.DomainProblem('domain-03.pddl', 'problem-03.pddl')
>>>

>>> domprob.initialstate()
{('adjacent', 'loc2', 'loc1'), ('unloaded', 'robr'), ('atl', 'robr', 'loc1'), ('unloaded', 'robq'), ('in', 'conta', 'loc1'), ('atl', 'robq', 'loc2'), ('adjacent', 'loc1', 'loc2'), ('in', 'contb', 'loc2')}
>>>

>>> list( domprob.operators() )
['load', 'unload', 'move']
>>>

>>> list( domprob.ground_operator('move') )
[<pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>, <pddlpy.pddl.Operator object at 0x10a968438>]
>>>

>>> list( domprob.ground_operator('move') )[0].precondition_pos
{('atl', 'robq', 'loc1'), ('adjacent', 'loc1', 'loc1')}
>>> 
```
The pddl files are examples obtained from the course material.


### Other Resources ###

There are wonderful material at the the University of Edinburgh:
* [AI Planning MOOC Project Home Page](http://www.aiai.ed.ac.uk/project/plan/ooc)
* [Index to access all course materials and videos](http://media.aiai.ed.ac.uk/Project/AIPLAN)
* [Videos on YouTube](http://bit.ly/aiplanmooc)


### Using the PDDL .NET library ###

The .NET library is available from nuget as `pddlnet.dll`.


### Future development ###

* Implement the `:requirements` directive.
* Add more examples (a simple planner maybe?).
* Add API documentation.
* More unit tests.
* Java version (it will be published in Java Central Repository).


### Adavanced ###

In case you want to tweak the grammar, add other target languages or modify the library you will need build this project from the repository sources.

#### Prerequisites

* Install ANTLR version 4.
    I used `brew install antlr4` (a Mac). Your mileage may vary depending on your environment.
* Install Python 3 (it works with Python 2 too).
    For this I also used brew.
* Install antlr4 runtime.
    `pip install antlr4-python3-runtime` (or `antlr4-python2-runtime` if building for Python 2)
* The package is built using wheel.
    `pip install wheel`
* mono development.
* Antlr4.Runtime.Standard.dll

#### Building

* Checkout the repository.
* Edit the Makefile to configure PATHs.
* Run `make` (it includes tests.)
  If you are using Python 2 you will need to call `make pyversion=2`.

To build the .NET library you must download the Antlr4.Runtime.Standard.dll from www.antlr4.org and
place it under the pddlnet directory. Currently it works with 4.7.0
 
 
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



