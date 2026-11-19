# LLMs with and without pddlpy: results (M3)

What does an LLM gain from pddlpy? I measured it on 7 problems, each told
in plain English, with two models and three tool setups ("arms"). The short
answer, as of November 2026:

- **Checking a plan and proving there is none:** both models do this well
  on their own at these sizes. pddlpy adds a guarantee, not a better answer.
- **Finding the cheapest plan:** without tools, models often fail. With
  tools, they succeed. A model that writes its own Python search does at
  least as well as one that calls pddlpy, and on the largest problem it
  does better: pddlpy's search is too slow there.

So pddl-py's value today is as a **verifier**: `validate_plan` checks a plan
step by step, and a reported `unsolvable` comes from an exhausted search
space, not from reading a table. Its planners are not yet faster than the
search a frontier model writes for itself.

## Setup

Runs on 2026-11-17 with the playground in [`e2e/llm/`](../e2e/llm/README.md).

| | |
|---|---|
| Models | `gpt-6.1-sol` (frontier; ChatGPT subscription through the Codex CLI), `qwen/qwen3.8-27b` (small, dense 27B; OpenRouter) |
| Arms | `bare`: no tools. `python`: a sandboxed Python (Codex: its shell). `pddlpy`: the pddlpy MCP server and a way to write files |
| Repeats | 3 per scenario, arm and model |
| Grading | the answer is mapped to plan steps (regex, else `gpt-5-mini` at temperature 0) and checked with `validate_plan` against reference PDDL the model never sees. Pass: the optimal plan, or the right judgment |

Each arm gets the same English problem and must answer in English. The
system prompt names the tools, never a method.

## Results

Passes out of 3, as `bare / python / pddlpy`:

| Scenario | What the model must do | gpt-6.1-sol | qwen3.8-27b |
|---|---|---|---|
| `courier-check` | find the bad step in a 20-step plan (a one-way road driven backwards) | 3 / 3 / 3 | 3 / 3 / 3 |
| `logistics-check` | find the bad step in a 26-step plan (a truck that moved 12 steps earlier) | 3 / 3 / 3 | 3 / 3 / 3 |
| `courier-unsolvable` | notice that no road leads to a destination | 3 / 3 / 3 | 3 / 3 / 3 |
| `courier-budget` | prove that the cheapest route (27) exceeds a budget of 26 | 3 / 3 / 3 | 3 / 3 / 1 |
| `maintenance-improve` | improve a 3-day schedule to 2 (10 planes) | 3 / 3 / 3 | 3 / 3 / 2 |
| `maintenance-improve-30` | improve a 5-day schedule to 4 (30 planes; the optimum shares no day with the proposal) | 2 / 3 / 3 | 1 / 2 / 3 |
| `maintenance-improve-60` | improve a 7-day schedule to 6 (60 planes, 8 days, 6 airports) | 1 / 3 / 3 | 0 / 2 / 1 |

Earlier, single runs on `courier-parcels` (deliver three parcels over 28
one-way tolled roads; optimum 27): `bare` gpt-6.1-sol answered 30, its
`python` and `pddlpy` arms 27.

Raw tables and selected transcripts: [`e2e/llm/runs/2026-11-17/`](../e2e/llm/runs/2026-11-17/).

## What the transcripts show

- **The judgment tasks are solved by reading.** Both models track the
  truck in `logistics-check` and compute the cheapest route before
  comparing it with the budget in `courier-budget`, without tools.
- **Optimization is where `bare` fails.** On the 30- and 60-plane schedules
  the models without tools often keep the proposal, give a schedule that
  misses planes, or (qwen) spend their whole reasoning budget without
  answering.
- **Models with Python write a correct search.** On the 60-plane schedule,
  gpt-6.1-sol's `python` arm writes an exhaustive search with pruning and
  answers in about 35 seconds.
- **pddlpy's planners are slow on set cover.** On the 60-plane schedule,
  `gbfs` needs about 400 s, `astar` about 600 s, and `ucs` does not finish
  in 600 s (about 230 states per second, most of the time in the hFF
  heuristic). qwen's one success came from `astar` with a 900 s timeout it
  chose itself. gpt-6.1-sol called `gbfs` with a 20 s timeout, got an 8-day
  schedule, then found the 6-day one with its own search and used pddlpy's
  `validate_plan` to check it.
- **PDDL is a cost for a small model.** qwen's `pddlpy` arm twice ran out of
  turns writing the numeric PDDL for `courier-budget`.

## Caveats

- **The Codex arms are not strict.** Codex routes every tool call, MCP
  included, through its JavaScript code mode, so gpt-6.1-sol's `python` and
  `pddlpy` arms can also compute in JavaScript, and on the 60-plane schedule
  it did. qwen's arms, through OpenRouter, hold strictly.
- **Codex adds its own agent prompt.** The two models do not see the same
  system prompt.
- **Small samples.** 3 repeats per cell; one model of each size.
- **Grading uses an LLM.** `gpt-5-mini` maps prose answers to plan steps.
  Two grader bugs were found and fixed during these runs (an unsolvable
  answer that also shows a relaxed plan; empty extractor replies); every
  table above was regraded with the fixed grader (`playground.py regrade`).

## What this means for pddl-py

1. **Lead with verification.** A checked plan and a proof of unsolvability
   are useful at any size, and the models already call `validate_plan` on
   their own answers when they have it.
2. **The built-in solver must get faster before it can claim the medium
   tier.** On the 60-plane schedule, a model's own Python beats it. This is
   the target for the search work (M5): set-cover-like problems, where
   hFF guidance is weak and a bounding search wins.
