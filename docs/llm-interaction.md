# An LLM and pddlpy, working together (#99)

LLMs are excellent **translators** and unreliable **planners**. They turn a
problem told in plain language into formal PDDL very well, but producing the
plan itself requires systematic search — and when costs are involved, a
plausible-sounding answer is not the same as the *cheapest* one. A classical
solver is the opposite: it cannot read your problem, but its answer comes
with a guarantee.

This page walks through the division of labour: **the LLM translates, pddlpy
solves, the LLM translates back.** The point is deliberately model-agnostic.
Frontier models keep getting better at planning, and this library does not
compete with them — it doesn't have to. Whether you drive it from a
top-of-the-line model or a small open-source one running locally, the solver
contributes the same thing the LLM cannot: a **provably optimal** answer.
The weaker the model, the more the solver adds; the stronger the model, the
cheaper it is to let the solver settle what would otherwise need a long,
unverifiable chain of reasoning.

> **What is simulated and what is real.** The conversation below is a
> *simulation* — a scripted illustration of the back-and-forth, not a
> transcript of one specific model (any LLM wired to the
> [CLI](../README.md#command-line-interface), the
> [MCP server](../README.md#mcp-server) or the
> [Agent Skill](../skills/pddlpy/SKILL.md) can play this role). Every
> **command and output, however, is real**: the PDDL files live in
> [`examples/pddl/`](../examples/pddl/), the outputs were produced by
> `pddlpy` 1.1, and a unit test keeps them honest.

## 1. The user states the problem

> **User:** A courier is at the **depot** and must deliver a parcel to
> **town**, spending as little as possible on tolls. The direct highway
> costs **10**. There's a route through the **junction**: 5 to get there,
> then 6 into town. And there's a back-road chain: **riverside** (2), then
> the **old bridge** (2), then into town (3). Roads are one-way. What's the
> cheapest route?

Small as it is, this is an *optimization* problem. An answer is only correct
if no cheaper route exists — something you can't see from the answer itself.

## 2. The LLM answers directly (and why you shouldn't settle for that)

> **LLM (answering from intuition):** Take the route through the junction:
> 5 + 6 = **11**, cheaper than the 10 highway... actually, comparing again,
> take the **direct highway for 10** — it beats the junction route.

The highway *does* beat the junction route — the decoy did its job — and yet
**10 is not the answer**: the three-hop back road costs 2 + 2 + 3 = **7**. On
five places you can check this by hand. On fifty, you cannot, and the LLM's
answer doesn't come with a proof either way. (This failure mode is
well-documented; see the [references](#references) below.)

## 3. The LLM translates the problem to PDDL instead

> **LLM:** Rather than trusting my arithmetic, let me write this down
> formally and let a solver find the optimum.

It emits two files — a *domain* (what actions exist) and a *problem* (this
particular map and goal): [`courier-domain.pddl`](../examples/pddl/courier-domain.pddl)
and [`courier-problem.pddl`](../examples/pddl/courier-problem.pddl). The
essence:

```lisp
(:action drive
  :parameters (?from - place ?to - place)
  :precondition (and (at ?from) (road ?from ?to))
  :effect (and (not (at ?from)) (at ?to)
               (increase (total-cost) (toll ?from ?to))))
```

```lisp
(:init (at depot)
  (road depot town)          (= (toll depot town) 10)
  (road depot junction)      (= (toll depot junction) 5)
  (road junction town)       (= (toll junction town) 6)
  (road depot riverside)     (= (toll depot riverside) 2)
  (road riverside oldbridge) (= (toll riverside oldbridge) 2)
  (road oldbridge town)      (= (toll oldbridge town) 3)
  (= (total-cost) 0))
(:goal (at town))
(:metric minimize (total-cost))
```

## 4. The LLM checks its own translation

Freshly written PDDL deserves a lint before a solve — a typo'd predicate or
an undeclared object would otherwise surface as a confusing "no plan":

```console
$ pddlpy validate courier-domain.pddl courier-problem.pddl
{
  "valid": true,
  "issues": []
}
```

(Had it mistyped `raod`, `validate` would exit `1` and name the undeclared
predicate — the fix-loop for agent-written PDDL. See the
[README](../README.md#command-line-interface).)

## 5. The solver finds the optimum

`ucs` is uniform-cost search: cost-optimal for `:action-costs` domains.

```console
$ pddlpy solve courier-domain.pddl courier-problem.pddl --planner ucs
{
  "planner": "ucs",
  "solved": true,
  "cost": 7.0,
  "length": 3,
  "steps": [
    {"action": "drive", "args": {"?from": "depot",     "?to": "riverside"}},
    {"action": "drive", "args": {"?from": "riverside", "?to": "oldbridge"}},
    {"action": "drive", "args": {"?from": "oldbridge", "?to": "town"}}
  ]
}
```

Not an opinion: no cheaper plan exists in this model.

## 6. The LLM translates the plan back

> **LLM:** The cheapest delivery costs **7 tolls**, not 10: drive from the
> depot to **riverside** (2), cross the **old bridge** (2), and continue
> into **town** (3). The direct highway (10) and the junction route (11)
> are both more expensive.

This last step is the easy direction — turning three JSON steps back into a
sentence — and it's where the LLM shines regardless of its size.

## Running it yourself

The same loop works over any of the three surfaces:

```bash
uvx pddlpy validate courier-domain.pddl courier-problem.pddl   # zero-install CLI
uvx pddlpy solve    courier-domain.pddl courier-problem.pddl --planner ucs
```

or give an agent the `validate` / `solve` tools via the MCP server
(`pddlpy-mcp`), or install the Agent Skill
(`npx skills add hfoffani/pddl-lib`) so a coding agent knows this recipe.

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
