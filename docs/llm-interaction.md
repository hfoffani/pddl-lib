# An LLM and pddlpy, working together (#99, #106)

LLMs are excellent **translators** and unreliable **planners**. They turn a
problem told in plain language into formal PDDL very well, but producing the
plan itself requires systematic search — and when costs are involved, a
plausible-sounding answer is not the same as the *cheapest* one. A classical
solver is the opposite: it cannot read your problem, but its answer comes
with a guarantee.

This page shows the division of labour on a real, captured conversation:
**the LLM translates, pddlpy solves, the LLM translates back.** The point is
deliberately model-agnostic. Frontier models keep getting better at planning,
and this library does not compete with them — it doesn't have to. Whether you
drive it from a top-of-the-line model or a small open-source one running
locally, the solver contributes the same thing the LLM cannot: a **provably
optimal** answer. The weaker the model, the more the solver adds; the
stronger the model, the cheaper it is to let the solver settle what would
otherwise need a long, unverifiable chain of reasoning.

> **How this was captured.** Everything below is a *real transcript* —
> model **`qwen/qwen-2.5-72b-instruct`**, captured **2026-07-13** by the
> manual end-to-end harness in [`e2e/llm/`](../e2e/llm/) (the raw capture is
> [committed next to it](../e2e/llm/transcripts/qwen_qwen-2.5-72b-instruct-20260713-102438.md)).
> The model received the problem plus tools: a local `write_file` and the
> pddlpy **MCP server** (`uvx --from "pddlpy[mcp]" pddlpy-mcp` — the
> published package in a transient environment). Tool outputs are verbatim;
> PDDL is re-indented for readability, nothing else edited. An earlier round
> with the same model was *unsound* — it invented PDDL cost syntax and never
> reached a valid plan — which is the thesis in miniature: the tools, not
> the model, carry the guarantee.

## 1. The user states the problem

> **User:** A courier is at the depot and must deliver a parcel to town,
> spending as little as possible on tolls. The direct highway costs 10.
> There's a route through the junction: 5 to get there, then 6 into town.
> And there's a back-road chain: riverside (2), then the old bridge (2),
> then into town (3). Roads are one-way. What's the cheapest route?

Small as it is, this is an *optimization* problem. An answer is only correct
if no cheaper route exists — something you can't see from the answer itself,
and exactly the kind of question direct LLM planning gets confidently wrong
(see the [references](#references)). So the system prompt tells the model:
*"Do not compute the plan yourself — your arithmetic is not a proof."*

## 2. The model translates the problem to PDDL

Its first tool calls write two files. The domain:

```lisp
(define (domain courier)
  (:requirements :strips :action-costs :fluents)
  (:types location - object)
  (:predicates
    (at ?l - location)
    (road ?from - location ?to - location))
  (:functions
    (total-cost)
    (toll ?from - location ?to - location))
  (:action drive
    :parameters (?from - location ?to - location)
    :precondition (and (at ?from) (road ?from ?to))
    :effect (and (not (at ?from)) (at ?to)
                 (increase (total-cost) (toll ?from ?to)))))
```

and the problem — a faithful translation of the map, ending in
`(:metric minimize (total-cost))`:

```lisp
(define (problem courier-delivery) (:domain courier)
  (:objects depot town junction riverside oldbridge - location)
  (:init
    (at depot)
    (road depot town)          (= (toll depot town) 10)
    (road depot junction)     (= (toll depot junction) 5)
    (road junction town)      (= (toll junction town) 6)
    (road depot riverside)    (= (toll depot riverside) 2)
    (road riverside oldbridge) (= (toll riverside oldbridge) 2)
    (road oldbridge town)     (= (toll oldbridge town) 3)
    (= (total-cost) 0))
  (:goal (at town))
  (:metric minimize (total-cost)))
```

## 3. The toolchain pushes back — and the model fixes it

The model calls `validate` (clean) and then `solve` with the cost-optimal
`ucs` planner. The solver *refuses*:

```json
{"valid": true, "issues": []}
```
```
Error executing tool solve: domain uses typing but does not declare a
matching requirement (one of [':adl', ':typing'])
```

The domain used `(:types ...)` without declaring `:typing` — caught by
pddlpy's requirements enforcement (#9). The model reads the error and
responds, verbatim:

> **Assistant:** I've encountered an error indicating that the domain file
> does not declare the `:typing` requirement, which is necessary for the
> planner to recognize the types I've defined. I will correct this and
> re-run the validation and solve steps.

It rewrites one line — `(:requirements :strips :action-costs :fluents
:typing)` — re-validates, and re-solves. This machine-checkable fix loop is
the whole reason `validate` and structured errors exist (#94): the model
never needs a human to tell it what's wrong.

## 4. The solver finds the optimum

```json
{"planner": "ucs", "solved": true, "cost": 7.0, "length": 3,
 "steps": [{"action": "drive", "args": {"?from": "depot",     "?to": "riverside"}},
           {"action": "drive", "args": {"?from": "riverside", "?to": "oldbridge"}},
           {"action": "drive", "args": {"?from": "oldbridge", "?to": "town"}}]}
```

Not an opinion: no cheaper plan exists in this model. The intuitive answers —
the direct highway (10) and the junction route (5+6 = 11) — both lose to the
three-hop back road (2+2+3 = 7).

## 5. The model translates the plan back

> **Assistant:** The cheapest route for the courier to deliver the parcel to
> town is via the back-road chain: from the depot to riverside, then to the
> old bridge, and finally into town. The total cost of this route is 7 toll
> units.

That closing step — three JSON steps into a sentence — is the easy direction,
where an LLM of any size shines.

## Running it yourself

The curated reference version of this domain lives in
[`examples/pddl/`](../examples/pddl/) (`courier-domain.pddl` /
`courier-problem.pddl`), pinned by a unit test:

```bash
uvx pddlpy validate courier-domain.pddl courier-problem.pddl   # zero-install CLI
uvx pddlpy solve    courier-domain.pddl courier-problem.pddl --planner ucs
```

To reproduce the *conversation* (needs an OpenRouter key; non-deterministic):

```bash
export OPENROUTER_API_KEY=...
make e2e-llm MODEL=qwen/qwen-2.5-72b-instruct
```

or give any agent the same tools via the MCP server (`pddlpy-mcp`) or the
Agent Skill (`npx skills add hfoffani/pddl-lib`).

## References

- Liu et al., *LLM+P: Empowering Large Language Models with Optimal Planning
  Proficiency*, 2023 — [arXiv:2304.11477](https://arxiv.org/abs/2304.11477).
  The pipeline shown here: LLM translates NL→PDDL, a classical planner
  solves, the LLM narrates the plan.
- Valmeekam et al., *PlanBench: An Extensible Benchmark for Evaluating Large
  Language Models on Planning and Reasoning about Change*, NeurIPS 2023 —
  [arXiv:2206.10498](https://arxiv.org/abs/2206.10498). Systematic evidence
  that direct LLM planning degrades quickly with problem size and
  unfamiliar domains.
