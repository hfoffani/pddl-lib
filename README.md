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

As of today it supports Python 3.11 and up.

The orginal grammar file was authored by Zeyn Saigol from University of Birmingham. I cleaned up it, made it language agnostic and upgraded to ANTLR 4.

### NOTICE ###

While the parser does recognize durations you cannot recover these tags from Python.

### What this project is not? ###

The core of this library is a PDDL parser and object model — a simple helper API for users experimenting with their own planning algorithms. It ships a small **reference planner layer** (see _Planning API_ below) whose only job is to prove a stable, pluggable solver interface; it is **not** intended to compete with full planning systems such as Fast Downward or LAMA. For serious solving there are lots of complete packages available.

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
Python 3.11.7 (main, Feb 10 2024, 17:01:04)
[Clang 15.0.0 (clang-1500.1.0.2.5)] on darwin
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
> Note: `initialstate()` and `goals()` return a set of `Atom` objects, not
> tuples. Their `repr` looks like a tuple (as shown above), but use
> `atom.predicate` to get the list of symbols. By contrast, a *grounded*
> operator's `precondition_pos`/`effect_pos`/etc. are real tuples.

The pddl files are examples obtained from the course material.

You can also read the domain's declared requirements:

```python
>>> domprob.requirements()
{':strips', ':typing'}
```

### Planning API ###

Above the parser/object model sits an optional, strictly-layered planning
package (`pddlpy.planning`). It imports from the object model but never from
the grammar; the object model imports nothing from it.

It provides:

* `State` — an immutable, hashable set of ground atoms. `State.from_problem(dp)`
  builds the initial state; `state.applicable(operator)` and
  `state.apply(operator)` check/advance a grounded operator without any manual
  `Atom`/tuple casting; `state.satisfies(goals)` tests the goal.
* `Plan` — an ordered sequence of grounded actions with a `cost`.
* `GroundedTask` — grounds every operator once and exposes a `successors(state)`
  function and `is_goal(state)`; the shared component every planner reuses.
* `Planner` — the abstract solver contract, `solve(domainproblem) -> Plan | None`.
  Each planner declares `capabilities` (the `:requirements` it supports) and
  **fails fast** with `UnsupportedRequirementsError` when handed a domain
  beyond its subset.
* `registry` — register and look up planners by name.
* Three reference planners over STRIPS: `BFSPlanner` (`"bfs"`), `AStarPlanner`
  (`"astar"`, goal-count heuristic) and `GBFSPlanner` (`"gbfs"`).

```python
>>> import pddlpy
>>> from pddlpy.planning import get
>>> dp = pddlpy.DomainProblem('blocksworld-domain.pddl', 'blocksworld-problem.pddl')
>>> plan = get('astar').solve(dp)
>>> plan.cost
4
>>> plan.action_names()
[('pick-up', {'?x': 'b'}), ('stack', {'?x': 'b', '?y': 'c'}),
 ('pick-up', {'?x': 'a'}), ('stack', {'?x': 'a', '?y': 'b'})]
```

Registering your own planner needs no changes to the layers below:

```python
from pddlpy.planning import Planner, registry

class MyPlanner(Planner):
    capabilities = frozenset({':strips', ':typing'})
    def solve(self, domainproblem):
        task = self.prepare(domainproblem)   # runs requirement + capability checks
        ...

registry.register('mine', MyPlanner)
plan = registry.get('mine').solve(dp)
```

### Other Resources ###

There are wonderful material at the the University of Edinburgh:
* [AI Planning MOOC Project Home Page](http://www.aiai.ed.ac.uk/project/plan/ooc)
* [Index to access all course materials and videos](http://media.aiai.ed.ac.uk/Project/AIPLAN)
* [Videos on YouTube](http://bit.ly/aiplanmooc)

### Future development ###

* Numeric fluents (`:functions`, numeric preconditions/effects).
* Action costs (`total-cost`) and cost-aware search.
* Durative actions (recover duration tags into the object model).
* Heuristic improvements for the reference planners.

Done recently: case-insensitive keywords, `:requirements` capture/enforcement,
a planner interface with BFS/A*/GBFS reference planners, and a measured test
suite with full coverage of the object model.

### Advanced ###

In case you want to tweak the grammar, add other target languages or modify the library you will need build this project from the repository sources.

#### Prerequisites

* Install [uv](https://docs.astral.sh/uv/) - a fast Python package installer and resolver
* Install Python 3.11 or higher
* Install Java (required for ANTLR grammar compilation)

#### Building

* Checkout the repository
* Initialize the uv environment: `uv sync`
* ANTLR JAR will be downloaded automatically when building
* Run `make` or `make all` to test grammar and run Python tests
* Run `make build` to build distribution packages

#### Available Make Targets

* `make all` - Run grammar tests and Python tests (default)
* `make init` - Initialize uv environment
* `make test` - Run Python tests only
* `make build` - Build distribution packages (wheel and source dist)
* `make clean` - Remove build artifacts
* `make demo` - Run demo scripts
* `make pypitest` - Publish to TestPyPI
* `make pypipublish` - Publish to PyPI
* `make help` - Show all available targets

### Contribution guidelines ###

I'd appreciate any feedback you send like pull requests, bug reports, etc.

Please, use the issue tracker at will.

### Acknowledgments

* Michiaki Tatsubori [@tatsubori](https://github.com/tatsubori) added time-duration support.
* Yichen Wei [@waymao](https://github.com/waymao) fixed an old bug.

I'm very thankful!

### License ###

This project is publish under the
[Apache License](http://www.apache.org/licenses/LICENSE-2.0).

### Who do I talk to? ###

For questions or requests post an issue here or tweet me at
[@herchu](http://twitter.com/herchu)