# Solve baseline (M2)

How far pddl-py's built-in planners get on the IPC corpora, next to Fast
Downward, and what stops them first. Reproduce with `make baseline` (see
`tests/solve_baseline.py`); the per-run CSV and a longer summary, including
coverage per domain variant, land in `$CORPORA_DIR/results/baseline-t10-n1/`.

## Setup

- Pairs: the first problem of each domain variant in the pinned corpora
  (`CORPORA_PER_DOMAIN=1`): 477 pairs, 100 of them durative.
- Runners: `bfs`, `ucs`, `astar` on every pair; `temporal` and a plan-validator
  probe on durative pairs; Fast Downward `astar(lmcut())` (fd-opt) and
  `--alias lama-first` (fd-sat).
- Limits: 10 s wall clock per run (parse + ground + search for pddl-py,
  translate + search for FD), 2.5 GB resident memory, 6 runs in parallel.
- Machine: Apple Silicon laptop, 10 cores, 16 GB, Python 3.14. Date: 2026-11-15.

## Results

| runner | solved | unsolvable | limit | timeout | memout | refused | total |
|---|---|---|---|---|---|---|---|
| bfs | 127 | 4 | 172 | 20 | 1 | 153 | 477 |
| ucs | 129 | 4 | 176 | 20 | 1 | 147 | 477 |
| astar | 132 | 4 | 167 | 19 | 2 | 153 | 477 |
| temporal | 10 | | 20 | | 4 | 66 | 100 |
| fd-opt | 168 | | | 100 | | 209 | 477 |
| fd-sat | 305 | | | 15 | | 157 | 477 |

`limit` is the search stopping at the time limit by itself; `timeout` and
`memout` are runs killed from outside, with the phase they were in recorded.
FD's refusals are exit 31 (input it does not support: numeric fluents,
durative actions, 157) and, for lmcut, exit 34 (conditional effects, 52).

- Any pddl-py planner solves 142 pairs, any FD configuration 305.
- FD only: 176 pairs. pddl-py only: 13 (numeric and preference variants FD
  does not accept, plus tyreworld and pathways).
- Every plan pddl-py returned passed its own validator: no `invalid` rows and
  no crashes.

## Where pddl-py stops

On the 176 pairs FD solves and pddl-py does not, `astar` ended as:

| outcome | pairs |
|---|---|
| search limit | 143 |
| refused | 19 |
| timeout while grounding | 14 |

Grounding and parsing are cheap on most pairs (median 0.01 s and 0.04 s on runs
that reached the search). The 14 grounding timeouts are tetris, snake,
caldera, organic-synthesis and mystery-prime/mprime. The 19 refusals are
mostly domains that use a feature they do not declare (pddl-py's
requirement check is stricter than FD's) and files with syntax errors.

The search is the limit, and two things slow it:

1. **The heuristic.** On 150 pairs, `astar` stopped at the search limit and FD
   solved the pair. On 101 of those, lama-first solved the pair in fewer states
   than `astar` expanded within its 10 s at its own speed. lmcut did so on 39.
   Median: lama-first expands 470 states on these pairs, while `astar` stopped
   after a median of 3,700. With FD's guidance and today's speed, most of
   these pairs would be solved. Goal-count adds little over blind search:
   `astar` solves 132 pairs and `bfs` 127.
2. **The cost of an expansion.** It grows with the number of grounded actions.
   Median expansions per second by grounding-time quartile: 4,600, 1,100, 370,
   46. The median over all runs is 2,900 (FD lmcut: 4,200, with a far more
   expensive heuristic). A profile on rovers (2,478 grounded actions, 130
   expansions/s) splits the time about evenly:
   - `successors` tests every grounded action for applicability in every state;
   - each successor `State` re-normalizes all its atoms (`atom_tuple`).

   Derived-predicate domains are the extreme case: psr-large and psr-middle
   expand under 1 state per second.

**First bottleneck: the heuristic.** hFF with greedy best-first search (M6)
is the first lever. Successor generation and state construction come second:
an applicability index and an `apply` that does not rebuild the atom set are
cheaper than bitmask states and would recover most of the per-expansion
cost on large tasks. Grounding comes third.

## Temporal pairs

`temporal` solves 10 of 100 durative pairs. It reaches the search on 30 and
expands a median of 140 states per second there. The plan validator refuses
66 of the 100 durative pairs:

| cause | pairs |
|---|---|
| duration given by an expression only | 19 |
| duration expression + numeric conditions or effects | 20 |
| duration expression + other parts (quantified, conditional, equality, numeric) | 13 |
| syntax errors (#141) | 9 |
| equality conditions, e.g. `(over all (not (= ?a ?b)))` | 3 |
| numeric conditions or effects only | 2 |

Expression durations, `(= ?duration (f ...))`, appear in 52 of the 66 refused
pairs. They are the first T2 item to take on. Equality literals in durative
conditions are not modeled; that is a gap not yet on the T2 list.
