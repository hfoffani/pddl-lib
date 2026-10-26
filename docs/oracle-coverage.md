# Oracle coverage

Which external oracle checks pddlpy's behavior for each `:requirements`
key, and how much benchmark material there is to check it on (#153). The
checks live in `tests/test_oracle.py`. `make oracle` runs them locally, and
the [Oracle workflow](../.github/workflows/oracle.yaml) runs them weekly,
on demand, and on pushes to `main` that touch parsing.

## The oracles

| Oracle | Role | Checks |
|---|---|---|
| Fast Downward (translator + `astar(blind())`) | Reference parser and planner for classical PDDL | pddlpy accepts and rejects the same files; FD's plans replay in pddlpy; FD and pddlpy agree on solvable vs unsolvable |
| VAL | **Primary plan validator** | FD's plans and pddlpy's plans (`astar`, or `temporal` for durative domains) are valid |
| INVAL | Second plan validator | The plan fixtures (`tests/corpus/ipc/*/plans/`) are valid or invalid as labeled |

VAL is the primary plan oracle because it covers temporal plans, which
INVAL does not. Agreement between VAL and INVAL on the fixtures is the
cross-check. Plan-validation agreement with pddlpy itself comes with
`validate_plan` (roadmap step 3).

FD only checks domains whose `:requirements` all fall within its
translator's list. Its translator refuses any other key, so those domains
are skipped, not compared. Grounded operator counts are never compared,
because FD prunes by reachability.

## Coverage map

*FD* and *VAL* show the checks that apply to a domain declaring the key.
*FD plans* and *pddlpy plans* name whose plans VAL validates; a dash means
no oracle checks that key. pddlpy plans exist only where a pddlpy planner
accepts the key (see [pddl-support.md](pddl-support.md)). Corpus columns
give domain variants / problems that declare the key. The pinned corpora
are `potassco/pddl-instances@cf19edf` and
`AI-Planning/classical-domains@4bd0b42` (`make corpora`). *Subset* counts
the committed pairs in `tests/corpus/ipc/`.

| Requirement | FD | VAL | INVAL | potassco | classical | Subset |
|---|---|---|---|---|---|---|
| (none) | yes | FD plans, pddlpy plans | fixtures | 3 / 80 | – | 1 |
| `:strips` | yes | FD plans, pddlpy plans | – | 89 / 2925 | 42 / 1813 | 7 |
| `:typing` | yes | FD plans, pddlpy plans | fixtures | 285 / 7583 | 114 / 3533 | 20 |
| `:negative-preconditions` | yes | FD plans, pddlpy plans | – | 12 / 242 | 44 / 1704 | 2 |
| `:disjunctive-preconditions` | yes | FD plans, pddlpy plans | – | – | 13 / 706 | 0 |
| `:equality` | yes | FD plans, pddlpy plans | – | 54 / 1271 | 27 / 798 | 6 |
| `:existential-preconditions` | yes | FD plans, pddlpy plans | – | 1 / 15 | – | 1 |
| `:universal-preconditions` | yes | FD plans, pddlpy plans | – | 1 / 15 | – | 1 |
| `:quantified-preconditions` | yes | FD plans, pddlpy plans | – | 1 / 30 | – | 1 |
| `:conditional-effects` | yes | FD plans, pddlpy plans | – | 12 / 265 | 22 / 1086 | 2 |
| `:adl` | yes | FD plans, pddlpy plans | – | 55 / 1980 | 4 / 120 | 9 |
| `:derived-predicates` | yes | FD plans | – | 6 / 267 | 4 / 196 | 1 |
| `:action-costs` | yes | FD plans, pddlpy plans | fixtures | 87 / 1957 | 69 / 1537 | 3 |
| `:fluents`, `:numeric-fluents` | – | pddlpy plans | – | 70 / 2013, 12 / 360 | – | 7, 1 |
| `:durative-actions` | – | pddlpy plans | – | 94 / 2500 | – | 7 |
| `:duration-inequalities` | – | – | – | 2 / 40 | – | 1 |
| `:timed-initial-literals` | – | – | – | 6 / 221 | – | 1 |
| `:preferences` | – | – | – | 20 / 418 | – | 1 |
| `:constraints` | – | – | – | 14 / 308 | – | 2 |
| `:goal-utilities` | – | – | – | 9 / 270 | – | 1 |
| `:domain-axioms` | – | – | – | 1 / 30 | – | 1 |

No oracle covers the last six rows. pddlpy does not solve them, and FD
refuses them. The golden files (`make golden`) and `make corpora-test`
still record what pddlpy makes of those domains.

## Sampling

A full pass over every pair (about 14,600) takes many hours, mostly in
pddlpy's grounding, so CI samples: `CORPORA_PER_DOMAIN` keeps the first N
problems of each domain variant (the smallest, by IPC numbering). The
workflow defaults to 5 for `corpora-test` and 2 for the oracle checks, and
`workflow_dispatch` takes other values (0 means all). The per-pair
snapshots are uploaded as a workflow artifact and never committed.
