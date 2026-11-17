# Solve baseline (M2)

How far pddl-py's built-in planners get on the IPC corpora, next to Fast
Downward, and what stops them first. Reproduce with `make baseline` (see
`tests/solve_baseline.py`), with the limits below:

```bash
BASELINE_MEMORY_GB=2.5 BASELINE_JOBS=6 make baseline                    # first pass
CORPORA_PER_DOMAIN=3 BASELINE_TIMEOUT=60 BASELINE_MEMORY_GB=2.5 BASELINE_JOBS=6 make baseline
```

A rerun resumes the CSV in the output directory and refuses to mix in other
limits. The per-run CSV and a longer summary, including
coverage per domain variant, land in `$CORPORA_DIR/results/baseline-t10-n1/`
(first pass) and `baseline-t60-n3/` (the longer pass at the end, the reference
later milestones are measured against).

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

- `bfs`, `ucs` or `astar` solves 142 pairs, 152 with `temporal`. Any FD
  configuration solves 305.
- FD only: 176 pairs. pddl-py only: 23 (durative, numeric and preference
  variants FD does not accept, plus tyreworld and pathways).
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

## Longer pass: 60 s, 3 per domain variant

Same runners and limits as above, with 60 s per run and the first three
problems of each domain variant:
1,430 pairs, 300 of them durative, about 6 h. Date: 2026-11-15.

| runner | solved | unsolvable | limit | timeout | memout | refused | total |
|---|---|---|---|---|---|---|---|
| bfs | 344 | 12 | 446 | 26 | 145 | 457 | 1430 |
| ucs | 339 | 12 | 379 | 24 | 237 | 439 | 1430 |
| astar | 364 | 12 | 395 | 24 | 178 | 457 | 1430 |
| temporal | 26 | | 64 | | 12 | 198 | 300 |
| fd-opt | 499 | | | 306 | 1 | 624 | 1430 |
| fd-sat | 908 | | | 52 | 1 | 469 | 1430 |

- `bfs`, `ucs` or `astar` solves 383 pairs, 409 with `temporal`. Any FD
  configuration solves 908. FD only: 556 pairs; pddl-py only: 57, the same
  kinds of variant as in the first pass.
- 1,076 plans returned by pddl-py, all accepted by its validator.

The first pass holds up:

1. **More time barely helps.** On the 477 pairs of the first pass, six times
   the budget takes `astar` from 132 to 145 solved and any pddl-py planner
   from 152 to 167. fd-sat goes from 305 to 308: what it solves, it solves
   fast (36 of its 908 plans took over 10 s).
2. **The heuristic is still the first bottleneck.** `astar` hit the search
   limit on 352 pairs that FD solved. On 281 of them lama-first needed fewer
   states than `astar` expanded, and lmcut did on 111. Median: 446 states for
   lama-first, 21,000 for `astar` before it stopped.
3. **Memory is the next wall.** The 10 s pass had almost no memouts. At 60 s,
   `astar` runs out of its 2.5 GB in the search on 137 pairs, after a median
   of 30 s; `ucs` on 200. On the 556 FD-only pairs, `astar` ends at the search
   limit on 343 and out of memory in the search on 111. Smaller states (the
   bitmask representation) and a lighter search node matter for memory, not
   just speed.
4. **Expansion speed** has the same shape: the median falls from 2,900 to
   1,800 expansions/s because the second and third problems of each variant
   are larger, and it drops by two orders of magnitude from the cheapest to
   the most expensive grounding quartile.
5. **Grounding** kills runs on the same domains as before (tetris, snake,
   caldera, organic-synthesis, mystery-prime/mprime, hand-coded depots).

On the durative pairs, `temporal` solves 26 of 300 and the plan validator
refuses 198 (66 %, as in the first pass). Expression durations appear in 156
of the 198, equality conditions in 30, syntax errors (#141) in 27. Order of
work unchanged: hFF with greedy best-first search (M6) first, then states that
are cheaper to build and smaller to store.

## After hFF: `gbfs` on the 60 s pass

`gbfs` now searches on hFF (`pddlpy/planning/relaxed.py`). It ran alone,
under the same limits as the longer pass (60 s, 3 per domain variant,
2.5 GB, 6 jobs; date: 2026-11-17), into `baseline-t60-n3-gbfs/`; the other
runners are unchanged. The sample has one more pair since a duplicated
satellite pair was removed, so the comparison uses the 1,430 pairs both runs
share.

| | gbfs (hFF) | astar | fd-sat |
|---|---|---|---|
| solved | 523 | 364 | 908 |
| search limit | 336 | 395 | |
| memout in the search | 46 | 137 | |

- Any pddl-py planner now solves 583 pairs, up from 409. FD-only pairs fall
  from 556 to 389.
- `gbfs` solves 184 pairs `astar` does not; `astar` solves 25 that `gbfs`
  does not.
- No `gbfs` run called a pair unsolvable that FD solves. All 523 plans
  passed the validator.
- On the 339 pairs both solve, `gbfs` expands a median of 12 states, `astar`
  699. Its plans cost what FD's optimal plans cost at the median (379 pairs);
  the worst is 8 times as expensive.
- Only 29 of the 523 plans took over 10 s: as before, more time adds little.
- Fewer states also means less memory: search memouts drop from 137 to 46.

What stops `gbfs` now, on the 389 FD-only pairs: the search limit on 290,
grounding (time or memory) on 31, memory in the search on 26, refusals on the
rest. On 173 of those 290, lama-first solved the pair in fewer states than
`gbfs` expanded. Two levers remain:

1. **Expansion speed.** hFF is computed for every generated state: `gbfs`
   expands a median of 630 states per second, against `astar`'s 1,800. Lazy
   evaluation (compute h when a state is expanded, not generated) and
   cheaper successor generation and states are the next step.
2. **Guidance.** lama-first adds landmarks and preferred operators. Preferred
   operators come from the relaxed plan hFF already builds, so they are the
   cheaper of the two.

## hFF speed and tie-breaking

Four changes on the `gbfs` above, then `gbfs` and `astar` rerun under the
same limits (60 s, 3 per domain variant, 2.5 GB, 6 jobs; date: 2026-11-17)
into `baseline-t60-n3-gbfs-speed/`. Each change was measured on its own: on
a fixed number of expansions when it leaves the search unchanged, and on
the 10 s / 1 per variant sample when it does not.

- **Reproducible search.** The grounded action order followed the string
  hash seed (grounding enumerates sets), and so did hFF's choice of
  supporters. Actions and hFF's atoms are now sorted. Before, `gbfs` solved
  182, 182 and 183 pairs of the 10 s sample under three seeds.
- **Same search, faster.** hFF drops atoms no action changes; successor
  generation tests only actions whose rarest needed atom holds (every
  planner benefits); successor states skip re-normalizing their atoms.
  Up to 36 % less time per expansion, none on some domains.
- **hFF's supporters by h_add.** Of the actions that reach an atom in the
  same layer, hFF keeps the one with the lowest h_add (1 plus its
  preconditions' costs). `gbfs` on the 10 s sample: 179 solved with
  alphabetical tie-breaking, 191 with h_add. Ordering by the problem's
  object declarations added nothing on top and was dropped.
- **Lazy evaluation**, h computed when a state is expanded instead of
  generated, solved no more pairs (181 vs 182) and was dropped.

On the 1,430 pairs shared with the passes above:

| | before | after | gained | lost | expansions/s |
|---|---|---|---|---|---|
| gbfs | 523 | 553 | 41 | 11 | 630 → 660 |
| astar | 364 | 390 | 26 | 0 | 1,700 → 10,500 |

- Any pddl-py planner solves 620 pairs (583 before); FD-only pairs fall from
  389 to 356. fd-sat solves 908.
- No `gbfs` unsolvable verdict on a pair FD solves; all 943 plans validate.
- `gbfs` spends what it gains in speed on the h_add tie-break: its
  expansions per second barely move, its guidance does.
- `astar` is six times faster per expansion and now runs out of memory
  instead of time: 427 memouts (178 before), 124 search limits (395).
  Smaller states matter for `astar` now. `gbfs` memouts: 80 → 105.

The 60 s numbers predate one fix: the action sort now reads arguments in
the operator's declared parameter order (review of PR #232). It reorders
actions on some domains; the 10 s sample moves from 191 to 193 for `gbfs`
and stays at 141 for `astar`.
