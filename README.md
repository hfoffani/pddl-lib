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

Durative actions are now recovered into the object model (see _Planning API_).
The reference planners, however, are non-temporal and do not solve durative
domains — that is documented as out of scope for this round.

### What this project is not? ###

The core of this library is a PDDL parser and object model — a simple helper API for users experimenting with their own planning algorithms. It ships a small **reference planner layer** (see _Planning API_ below) whose only job is to prove a stable, pluggable solver interface; it is **not** intended to compete with full planning systems such as Fast Downward or LAMA. For serious solving there are lots of complete packages available.

### Examples ###

In this repostory you'll find some PDDL examples files useful for testing purposes.
For instance, [domain-03.pddl](examples-pddl/domain-03.pddl)
and [problem-03.pddl](examples-pddl/problem-03.pddl)

#### Example showcase

The [`examples/`](examples/) directory holds a set of self-contained, runnable
scripts of increasing complexity, each demonstrating one capability against a
bundled PDDL domain in [`examples/pddl/`](examples/pddl/). Run them all with
`make examples`, or one at a time, e.g. `uv run python examples/01_parsing_basics.py`.

| # | Example | What it shows | Capability |
|---|---------|---------------|------------|
| 01 | [01_parsing_basics.py](examples/01_parsing_basics.py) | Parse a typed domain/problem; read objects, init, goals, operators and grounded operators | Core object model |
| 02 | [02_type_hierarchy.py](examples/02_type_hierarchy.py) | Multi-level `:types`, `types()` / `subtypes_of()`, supertype binding in grounding | Type hierarchies (#22) |
| 03 | [03_logical_operators.py](examples/03_logical_operators.py) | Top-level `and` / `or` connective and negative preconditions in the model | Logical operators (#13) |
| 04 | [04_planners.py](examples/04_planners.py) | The planner registry and BFS / A\* reference planners solving blocksworld and gripper | Planners (#1) |
| 05 | [05_numeric_and_costs.py](examples/05_numeric_and_costs.py) | Numeric fluents (fuel-aware planning) and action costs (UCS cost-optimality) | Numeric fluents (#11) + action costs (#3) |
| 06 | [06_durative.py](examples/06_durative.py) | Durative model, `DurativeState` `at start` applicability and validation — **not** temporally solved | Durative actions (#23) |

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

#### Type hierarchies and variable binding

A `:types` hierarchy (e.g. `airport - location`, `location - object`) is
honoured: a parameter typed with a supertype binds objects of any transitive
subtype, so multi-level domains such as logistics ground and solve. The
hierarchy is also exposed directly:

```python
>>> domprob.types()          # subtype -> direct supertype
{'airport': 'location', 'location': 'object', ...}
>>> domprob.subtypes_of('object')   # all transitive subtypes
{'location', 'airport', ...}
```

Grounding is performed by a pluggable variable **binder**. The default
`StaticPrunedBinder` prunes parameter bindings that can never be applicable by
joining the operator's *static* preconditions (predicates no action ever
modifies) against the initial state — sound, since a static predicate's truth
is fixed for the whole search. Pass `binder=CartesianBinder()` for the plain
full product, or supply your own:

```python
from pddlpy import DomainProblem
from pddlpy.binding import CartesianBinder, VariableBinder

dp = DomainProblem('domain.pddl', 'problem.pddl', binder=CartesianBinder())

class MyBinder(VariableBinder):
    def bind(self, dp, operator):
        # yield {param_name: object_name} dicts; helpers: dp.candidate_objects(t),
        # dp.static_predicates(), dp.initialstate(), dp.worldobjects()
        ...

dp.binder = MyBinder()
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

Numeric fluents (`:functions`, numeric preconditions/effects) are supported:
`DomainProblem.functions()` and `initial_numeric()` expose them, grounded
operators carry `precondition_num` / `effect_num`, and `State` tracks a numeric
valuation so the planners respect constraints like `(>= (fuel ?v) 10)` and
effects like `(decrease (fuel ?v) 5)`.

Action costs (`:action-costs`, `(increase (total-cost) ...)`, `(:metric minimize
(total-cost))`) are supported too. `DomainProblem.metric()` exposes the metric,
`Plan.cost` reports the accumulated `total-cost`, and `UniformCostPlanner`
(`"ucs"`) is cost-optimal — where `BFSPlanner` minimizes the number of actions,
`"ucs"` minimizes total cost.

Durative actions (`:durative-actions`) are recovered into a `DurativeAction`
type with time-tagged conditions (`at start` / `over all` / `at end`) and
effects (`at start` / `at end`) plus a duration. `DomainProblem.durative_operators()`
and `ground_durative_operator(name)` expose them. The reference planners are
non-temporal, so they do not solve durative domains — this is documented as out
of scope for now.

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

### Documentation ###

* [`docs/object-model.md`](docs/object-model.md) — full reference for the
  parser object model and the planning layer.
* [`skills/pddlpy/SKILL.md`](skills/pddlpy/SKILL.md) — an Agent Skill so coding
  agents can drive the library (parse, ground, plan).

### Other Resources ###

There are wonderful material at the the University of Edinburgh:
* [AI Planning MOOC Project Home Page](http://www.aiai.ed.ac.uk/project/plan/ooc)
* [Index to access all course materials and videos](http://media.aiai.ed.ac.uk/Project/AIPLAN)
* [Videos on YouTube](http://bit.ly/aiplanmooc)

### Future development ###

* A temporal planner that solves durative-action domains.
* Heuristic improvements for the reference planners.
* ADL (conditional effects, quantifiers) and a full and/or/not precondition tree.

Done recently: case-insensitive keywords, `:requirements` capture/enforcement,
a planner interface with BFS/A*/GBFS/UCS reference planners, numeric fluents
(`:functions`, numeric preconditions/effects), action costs (`total-cost` +
cost-aware search), durative-action recovery into the object model, and a
measured test suite with full coverage of the object model and planning layer.

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