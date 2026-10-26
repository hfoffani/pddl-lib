## pddl-lib ##

pddl-py (`pip install pddlpy`) is a PDDL toolkit for Python. It parses PDDL
domain and problem files with an ANTLR 4 grammar, builds an object model,
checks the files for common mistakes, and solves them with small reference
planners. You can drive it from Python, from the `pddlpy` command line, or
through an MCP server that LLM agents call as tools.

It runs on Python 3.11 and up.

### Project direction ###

I started pddl-py in 2015 as a PDDL parser with a simple object model, so
planning students and researchers could plug in their own search algorithms.
That is still in here and it still works.

What changed is who calls it. LLMs now write well-formed PDDL, but they are
unreliable at producing correct or optimal plans, at tracking state over many
steps, and at proving that a problem has no plan. Those are exactly the jobs a
PDDL tool does well. So the primary goal of pddl-py is now to be the
conformant PDDL toolkit that agents call to fill those gaps: parse, validate,
simulate and solve, through the CLI and the MCP server.

Researchers and app developers stay first-class users of the Python API. I am
not dropping that audience, I am adding a new one and letting it set the
priorities.

A few things follow from this:

* **Conformance target.** PDDL 1.2, 2.1, 2.2, 3.0 and 3.1. Support is partial
  today, and I publish it per `:requirements` keyword in
  [`docs/pddl-support.md`](docs/pddl-support.md), including what does not work.
* **Priorities.** I add requirements in the order that helps LLM use most.
* **Not a Fast Downward competitor.** The reference planners stay small and
  readable. Hard search will go to external solvers, not to a bigger planner
  inside this package.

### Install ###

```bash
pip install pddlpy            # library + `pddlpy` CLI
pip install "pddlpy[mcp]"     # also the MCP server (`pddlpy-mcp`)
```

`pddlpy` has no runtime dependencies: the ANTLR runtime (4.13.2, BSD-3-Clause)
is vendored in `pddlpy/_vendor/`, so it does not clash with packages that pin
another `antlr4-python3-runtime` version. `mcp` is an optional extra. Java is
not needed to install or use the package.

### Command-line interface ###

The `pddlpy` command has four subcommands. All of them print JSON on stdout,
so an agent or a shell pipeline can use them without writing Python:

```bash
pddlpy parse    domain.pddl problem.pddl            # object-model summary
pddlpy ground   domain.pddl problem.pddl pick-up    # grounded instances of one action
pddlpy solve    domain.pddl problem.pddl --planner ucs
pddlpy validate domain.pddl problem.pddl            # diagnostics (see below)
```

`solve` defaults to `astar`. `--planner` takes any registered planner: `bfs`,
`astar`, `gbfs`, `ucs` or `temporal`.

```bash
$ pddlpy solve tests/corpus/blocksworld-domain.pddl tests/corpus/blocksworld-problem.pddl | jq .cost
4
```

With `--planner temporal` each step also carries `start`, `duration` and
`end`, and the result has a top-level `makespan`:

```bash
$ pddlpy solve tests/corpus/temporal-weld-domain.pddl tests/corpus/temporal-weld-problem.pddl --planner temporal | jq -c .
{"planner":"temporal","solved":true,"cost":6.0,"makespan":6.0,"length":1,"steps":[{"action":"steady-weld","args":{"?p":"p1"},"start":0.0,"duration":6.0,"end":6.0}]}
```

Exit codes: `0` success, `1` the search finished without a plan or `validate`
found issues, `2` bad input (missing file, unknown operator, unsupported
`:requirements`).

`validate` is the feedback step for a write PDDL, validate, fix, solve loop.
A bare parse is not enough because ANTLR recovers from syntax errors and only
prints them to stderr. `validate` collects those syntax errors and also reports
atoms over undeclared predicates, ground atoms that name unknown objects,
operators that ground to zero instances, and malformed durative actions. For
example, after a typo in a blocksworld problem (`on-table` instead of
`ontable`):

```bash
$ pddlpy validate domain.pddl problem.pddl
{
  "valid": false,
  "issues": [
    {
      "severity": "error",
      "check": "undeclared_predicate",
      "message": "predicate 'on-table' is not declared in :predicates (used in :init)"
    }
  ]
}
```

### MCP server ###

The [Model Context Protocol](https://modelcontextprotocol.io) server exposes
the same four operations as tools: `parse`, `ground`, `solve` and `validate`.
They return the same JSON as the CLI.

```bash
pip install "pddlpy[mcp]"
pddlpy-mcp                   # runs on stdio
```

It speaks MCP 2026-07-28 and the earlier protocol versions 2024-11-05,
2025-03-26, 2025-06-18 and 2025-11-25, so older clients still connect.

Client configuration (e.g. Claude Desktop / Claude Code):

```json
{
  "mcpServers": {
    "pddlpy": { "command": "pddlpy-mcp" }
  }
}
```

The tools take filesystem paths to the domain and problem files. `solve` takes
an optional `planner` argument (`bfs`, `astar`, `gbfs`, `ucs` or `temporal`;
default `astar`). For an agent that translates natural language into PDDL,
`validate` gives the feedback for the fix loop.

For agents that work from files instead of MCP, there is also an Agent Skill in
[`skills/pddlpy/`](skills/pddlpy/SKILL.md).

**Why pair an LLM with a solver at all?** LLMs translate problems into PDDL
well but are unreliable at producing plans, let alone optimal ones. Handing the
search to a solver uses each for what it is good at.
[`docs/llm-interaction.md`](docs/llm-interaction.md) walks through a complete
example (natural language, PDDL, `pddlpy solve`, natural language) on a small
cost-optimal routing problem where the intuitive answer is wrong.
Background reading: *LLM+P* ([arXiv:2304.11477](https://arxiv.org/abs/2304.11477)),
the paper behind this pipeline, and *PlanBench*
([arXiv:2206.10498](https://arxiv.org/abs/2206.10498)) on why direct LLM
planning falls short.

### Supported :requirements ###

The state of the code today, checked against the parser and the planners, not a wish list, is in [`docs/pddl-support.md`](docs/pddl-support.md).

### Python API ###

```python
>>> import pddlpy
>>> domprob = pddlpy.DomainProblem('examples-pddl/domain-03.pddl', 'examples-pddl/problem-03.pddl')
>>> sorted(map(repr, domprob.initialstate()))
["('adjacent', 'loc1', 'loc2')", "('adjacent', 'loc2', 'loc1')", "('atl', 'robq', 'loc2')", "('atl', 'robr', 'loc1')", "('in', 'conta', 'loc1')", "('in', 'contb', 'loc2')", "('unloaded', 'robq')", "('unloaded', 'robr')"]
>>> list(domprob.operators())
['move', 'load', 'unload']
>>> moves = sorted(domprob.ground_operator('move'), key=lambda op: sorted(op.variable_list.items()))
>>> len(moves)
4
>>> moves[0].variable_list
{'?from': 'loc1', '?to': 'loc2', '?r': 'robq'}
>>> sorted(moves[0].precondition_pos)
[('adjacent', 'loc1', 'loc2'), ('atl', 'robq', 'loc1')]
>>> sorted(domprob.requirements())
[':strips', ':typing']
```

> Note: `initialstate()` and `goals()` return a set of `Atom` objects, not
> tuples. Their `repr` looks like a tuple, but `Atom` has no value equality:
> use `atom.predicate` to get the list of symbols, or
> `pddlpy.planning.atom_tuple` to compare. A *grounded* operator's
> `precondition_pos` / `effect_pos` / etc. are real tuples.

The files in [`examples-pddl/`](examples-pddl/) come from the course material
mentioned in [History](#history-and-acknowledgments).

#### Type hierarchies and variable binding

A `:types` hierarchy (e.g. `airport - location`, `location - object`) is
honoured: a parameter typed with a supertype binds objects of any transitive
subtype, so multi-level domains such as logistics ground and solve. The
hierarchy is also exposed directly:

```python
>>> dp = pddlpy.DomainProblem('tests/corpus/logistics-domain.pddl', 'tests/corpus/logistics-problem.pddl')
>>> dp.types()          # subtype -> direct supertype
{'truck': 'vehicle', 'airplane': 'vehicle', 'package': 'physobj', 'vehicle': 'physobj', 'airport': 'location', 'city': 'object', 'location': 'object', 'physobj': 'object'}
>>> sorted(dp.subtypes_of('object'))   # all transitive subtypes
['airplane', 'airport', 'city', 'location', 'package', 'physobj', 'truck', 'vehicle']
```

A pluggable variable **binder** does the grounding. The default
`StaticPrunedBinder` drops parameter bindings that can never apply, by joining
the operator's *static* preconditions (predicates no action changes) against
the initial state. That is sound because a static predicate's truth never
changes during search. It is why `move` above grounds to 4 instances instead
of the 8 of the full product. Pass `binder=CartesianBinder()` for the full
product, or supply your own:

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

#### Planning API

The planning package (`pddlpy.planning`) sits on top of the object model. It
imports the object model but never the grammar, and the object model imports
nothing from it.

It provides:

* `State`: an immutable, hashable set of ground atoms plus a numeric valuation.
  `State.from_problem(dp)` builds the initial state; `state.applicable(operator)`
  and `state.apply(operator)` check and advance a grounded operator without
  manual `Atom`/tuple casting; `state.satisfies(goals)` tests the goal.
* `Plan`: an ordered sequence of grounded actions with a `cost`.
* `GroundedTask`: grounds every operator once and exposes `successors(state)`
  and `is_goal(state)`. Every planner reuses it.
* `Planner`: the abstract solver contract, `solve(domainproblem) -> Plan | None`.
  Each planner declares `capabilities` (the `:requirements` it supports) and
  fails fast with `UnsupportedRequirementsError` when handed a domain beyond
  them.
* `registry`: register and look up planners by name.
* Five reference planners: `BFSPlanner` (`"bfs"`, fewest actions),
  `AStarPlanner` (`"astar"`, goal-count heuristic), `GBFSPlanner` (`"gbfs"`,
  greedy), `UniformCostPlanner` (`"ucs"`, cost-optimal) and `TemporalPlanner`
  (`"temporal"`, durative actions).

```python
>>> from pddlpy.planning import get
>>> dp = pddlpy.DomainProblem('tests/corpus/blocksworld-domain.pddl', 'tests/corpus/blocksworld-problem.pddl')
>>> plan = get('astar').solve(dp)
>>> plan.cost
4
>>> plan.action_names()
[('pick-up', {'?x': 'b'}), ('stack', {'?x': 'b', '?y': 'c'}),
 ('pick-up', {'?x': 'a'}), ('stack', {'?x': 'a', '?y': 'b'})]
```

Numeric fluents: `DomainProblem.functions()` and `initial_numeric()` expose
them, grounded operators carry `precondition_num` / `effect_num`, and `State`
tracks the numeric valuation, so the planners respect constraints like
`(>= (fuel ?v) 10)` and effects like `(decrease (fuel ?v) 5)`.

Action costs: `DomainProblem.metric()` exposes the metric and `Plan.cost`
reports the accumulated `total-cost`. `bfs` minimizes the number of actions;
`ucs` minimizes total cost.

Durative actions are parsed into a `DurativeAction` with time-tagged
conditions (`at start` / `over all` / `at end`), effects (`at start` /
`at end`) and a duration. `DomainProblem.durative_operators()` and
`ground_durative_operator(name)` expose them. The `temporal` planner solves
these domains. It checks `at start` conditions at the start point, `over all`
as an invariant across the duration, and `at end` at start + duration, under
sequential semantics: actions never overlap, and instantaneous actions run as
zero-duration steps. It returns a `TemporalPlan` whose `steps` carry start
times and durations, and whose `makespan` is the plan cost. See the
[requirements table](docs/pddl-support.md) for its limits.

```python
>>> dp = pddlpy.DomainProblem('tests/corpus/temporal-weld-domain.pddl', 'tests/corpus/temporal-weld-problem.pddl')
>>> plan = get('temporal').solve(dp)
>>> plan.makespan
6.0
>>> [(s.start, s.action.operator_name, s.duration) for s in plan.steps]
[(0.0, 'steady-weld', 6.0)]
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

### Examples ###

The [`examples/`](examples/) directory has self-contained, runnable scripts
of increasing complexity. Each one shows one capability against a bundled PDDL
domain in [`examples/pddl/`](examples/pddl/). Run them all with
`make examples`, or one at a time, e.g. `uv run python examples/01_parsing_basics.py`.

| # | Example | What it shows | Capability |
|---|---------|---------------|------------|
| 01 | [01_parsing_basics.py](examples/01_parsing_basics.py) | Parse a typed domain/problem; read objects, init, goals, operators and grounded operators | Core object model |
| 02 | [02_type_hierarchy.py](examples/02_type_hierarchy.py) | Multi-level `:types`, `types()` / `subtypes_of()`, supertype binding in grounding | Type hierarchies (#22) |
| 03 | [03_logical_operators.py](examples/03_logical_operators.py) | Top-level `and` / `or` connective and negative preconditions in the model | Logical operators (#13) |
| 04 | [04_planners.py](examples/04_planners.py) | The planner registry and BFS / A\* reference planners solving blocksworld and gripper | Planners (#1) |
| 05 | [05_numeric_and_costs.py](examples/05_numeric_and_costs.py) | Numeric fluents (fuel-aware planning) and action costs (UCS cost-optimality) | Numeric fluents (#11) + action costs (#3) |
| 06 | [06_durative.py](examples/06_durative.py) | Durative model, `DurativeState` `at start` applicability and validation. To solve durative domains use the `temporal` planner (see _Planning API_) | Durative actions (#23) |

More PDDL pairs for testing live in [`examples-pddl/`](examples-pddl/) and
[`tests/corpus/`](tests/corpus/).

### Documentation ###

* [`docs/object-model.md`](docs/object-model.md): full reference for the
  object model and the planning layer.
* [`docs/pddl-support.md`](docs/pddl-support.md): what each `:requirements`
  keyword supports today, and the known bugs.
* [`docs/llm-interaction.md`](docs/llm-interaction.md): worked example of an
  LLM and pddlpy splitting the work: translate, solve, translate back (#99).
* [`skills/pddlpy/SKILL.md`](skills/pddlpy/SKILL.md): an Agent Skill so coding
  agents can drive the library and the CLI.

### Roadmap ###

These are plans, not promises, and there are no dates. Roughly in order:

1. Vendor the ANTLR runtime so `pip install pddlpy` has zero runtime
   dependencies.
2. An oracle test harness against Fast Downward, VAL and INVAL on the IPC
   corpora.
3. Plan validation and plan simulation with structured diagnostics.
4. Decide whether to keep ANTLR or replace the parser, before the grammar
   grows.
5. Requirements by priority: goal-side ADL and `(either ...)`, timed initial
   literals, derived predicates, preferences, concurrent durative actions,
   trajectory constraints.
6. Duration inequalities, continuous effects, object fluents.
7. HDDL / HTN.

### History and acknowledgments ###

pddl-py started in 2015, inspired by the University of Edinburgh's Artificial
Intelligence Planning MOOC by Dr. Gerhard Wickler and Prof. Austin Tate. The
terms in the object model API (and the API itself) closely follow the ones the
lecturers used.

The original grammar was written by Zeyn Saigol from the University of
Birmingham. I cleaned it up, made it language agnostic and upgraded it to
ANTLR 4.

The Edinburgh course material is still worth your time:
* [AI Planning MOOC Project Home Page](http://www.aiai.ed.ac.uk/project/plan/ooc)
* [Index to access all course materials and videos](http://media.aiai.ed.ac.uk/Project/AIPLAN)
* [Videos on YouTube](http://bit.ly/aiplanmooc)

Contributors:

* Michiaki Tatsubori [@tatsubori](https://github.com/tatsubori) added time-duration support.
* Yichen Wei [@waymao](https://github.com/waymao) fixed an old bug.

I'm very thankful!

### Building from source ###

You only need this to change the grammar, add other target languages or work
on the library itself. Installing and using the package needs none of it.

#### Prerequisites

* [uv](https://docs.astral.sh/uv/)
* Python 3.11 or higher
* Java, only to change the grammar. The generated parser files are committed,
  so a fresh clone runs the tests without Java.

#### Building

* Clone the repository.
* Run `uv sync` to set up the environment.
* Run `make test` to run the Python tests.
* After changing `pddl.g4`, run `make pyparser` to regenerate the parser into
  `pddlpy/` (it downloads the ANTLR jar), and commit the regenerated files. CI
  fails if they don't match the grammar.
* Run `make` (or `make all`) to test the grammar (needs Java and `javac`) and
  run the Python tests.
* Run `make build` to build the wheel and sdist.

#### Available Make Targets

* `make all` - Run grammar tests and Python tests (default)
* `make init` - Initialize uv environment
* `make pyparser` - Generate the Python parser from `pddl.g4` (needs Java)
* `make test` - Run Python tests only
* `make coverage` - Run tests with a coverage report
* `make lint` - Lint with ruff
* `make typecheck` - Type-check with mypy
* `make build` - Build distribution packages (wheel and source dist)
* `make examples` - Run the example showcase
* `make clean` - Remove build artifacts
* `make demo` - Run demo scripts
* `make help` - Show all available targets

Publishing to PyPI happens only in GitHub Actions when a `v*` tag is pushed
(TestPyPI first, then PyPI, via [Trusted
Publishing](https://docs.pypi.org/trusted-publishers/)). See
[`.github/workflows/publish.yaml`](.github/workflows/publish.yaml). CI (tests,
100% coverage gate, lint, typecheck) runs on every pull request.

### Contribution guidelines ###

I'd appreciate any feedback you send like pull requests, bug reports, etc.

Please, use the issue tracker at will.

### License ###

This project is published under the
[Apache License](http://www.apache.org/licenses/LICENSE-2.0).

### Who do I talk to? ###

For questions or requests post an issue here or tweet me at
[@herchu](http://twitter.com/herchu)
