# IPC subset: sources

A curated subset of the International Planning Competition benchmarks, used
by the golden check (`tests/test_golden.py`, #153). Each directory holds one
domain variant: `domain.pddl`, problems `pNN.pddl`, and per problem the
golden file `pNN.json` (regenerate with `make golden`).

Every file is copied unmodified from
[potassco/pddl-instances](https://github.com/potassco/pddl-instances) at
commit `cf19edf7c53d1540ddbb396c642595e0926ee552`. `pNN.pddl` is upstream
`instances/instance-N.pddl`. Variants with one domain file per instance
contribute only instance 1, with its `domains/domain-1.pddl`.

`scripts/fetch-corpora.sh` (`make corpora`) fetches the full corpora at
pinned commits into the git-ignored `.corpora/`.

**License.** The upstream repository has no license file. The files are the
IPC benchmark sets, published by the competition organizers and
redistributed for research by planning.domains, Fast Downward's benchmark
repository and others. Credit belongs to the IPC organizers and the domain
authors named in each upstream `README.md`.

| Directory | Stands for | Upstream (`potassco/pddl-instances`) | Files |
|---|---|---|---|
| `gripper-round-1-strips` | no `:requirements` | `ipc-1998/domains/gripper-round-1-strips/` | instance-1 |
| `blocks-strips-typed` | `:strips :typing` | `ipc-2000/domains/blocks-strips-typed/` | instance-1, instance-2 |
| `satellite-strips-automatic` | `:strips :typing` | `ipc-2002/domains/satellite-strips-automatic/` | instance-1, instance-2 |
| `elevator-adl-full-typed` | `:adl` | `ipc-2000/domains/elevator-adl-full-typed/` | instance-1, instance-2 |
| `mystery-prime-round-1-adl` | `:quantified-preconditions` | `ipc-1998/domains/mystery-prime-round-1-adl/` | instance-1 |
| `umtranslog-2-numeric-hand-coded` | `:existential-preconditions :universal-preconditions :fluents` | `ipc-2002/domains/umtranslog-2-numeric-hand-coded/` | instance-1 |
| `hiking-sequential-optimal` | `:equality` | `ipc-2014/domains/hiking-sequential-optimal/` | instance-1 |
| `city-car-sequential-optimal` | `:conditional-effects :negative-preconditions :action-costs` | `ipc-2014/domains/city-car-sequential-optimal/` | instance-1 |
| `openstacks-sequential-optimal-strips` | `:action-costs` | `ipc-2008/domains/openstacks-sequential-optimal-strips/` | instance-1, domain-1 |
| `depots-numeric-automatic` | `:fluents` | `ipc-2002/domains/depots-numeric-automatic/` | instance-1, instance-2 |
| `openstacks-temporal-satisficing-numeric-fluents` | `:numeric-fluents :durative-actions` | `ipc-2008/domains/openstacks-temporal-satisficing-numeric-fluents/` | instance-1, domain-1 |
| `match-cellar-temporal-satisficing` | `:durative-actions` | `ipc-2011/domains/match-cellar-temporal-satisficing/` | instance-1, instance-2 |
| `rovers-time-automatic` | `:duration-inequalities` | `ipc-2002/domains/rovers-time-automatic/` | instance-1 |
| `psr-middle-derived-predicates-adl` | `:derived-predicates` | `ipc-2004/domains/psr-middle-derived-predicates-adl/` | instance-1 |
| `trucks-time-constraints-timed-initial-literals` | `:timed-initial-literals` | `ipc-2006/domains/trucks-time-constraints-timed-initial-literals/` | instance-1 |
| `tpp-preferences-simple` | `:preferences` | `ipc-2006/domains/tpp-preferences-simple/` | instance-1 |
| `trucks-time-constraints` | `:constraints` | `ipc-2006/domains/trucks-time-constraints/` | instance-1 |
| `pipesworld-metric-time-constraints` | `:constraints` (loader crash, #140) | `ipc-2006/domains/pipesworld-metric-time-constraints/` | instance-1 |
| `openstacks-net-benefit-optimal-adl` | `:goal-utilities` | `ipc-2008/domains/openstacks-net-benefit-optimal-adl/` | instance-1 |
| `logistics-round-1-adl` | `:domain-axioms` | `ipc-1998/domains/logistics-round-1-adl/` | instance-1 |
