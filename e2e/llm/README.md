# LLM + solver end-to-end

Two manual, non-deterministic tools, **never wired into CI**:

- `playground.py`: many scenarios × models × arms. Use it to explore.
- `harness.py`: the single courier run behind `docs/llm-interaction.md` (#106).

## Playground

Every arm gets the same English problem and must answer in English. Only the
tools differ:

| Arm | Tools | Shows |
|---|---|---|
| `bare` | none | what the model learned in training |
| `python` | `run_python`: base interpreter, stdlib only, temp dir, 60 s timeout, macOS `sandbox-exec` (no network, no writes outside the temp dir, no reads under `/Users`) | whether the model writes a solver on its own |
| `pddlpy` | `write_file` + the pddlpy MCP tools (this checkout) | the pddl-lib route |

System prompts only name the tools, never a method. The answer is graded
against the scenario's reference PDDL. `(action args)` lines are read
directly; otherwise an extractor model (`--grader-model`, temperature 0)
transcribes the answer into those lines, and then `validate_plan` decides:
`optimal`, `suboptimal`, `goal-not-reached`, `invalid` or `unparseable`.

```bash
export OPENROUTER_API_KEY=...
P="uv run --with mcp,httpx python e2e/llm/playground.py"
$P list                      # scenarios + optimum
$P show maintenance          # the English text the model sees
$P check --plan              # solve every reference problem
$P run maintenance logistics --arm bare,python,pddlpy \
   --model openai/gpt-5,qwen/qwen3-235b-a22b --repeats 3
$P run courier --arm bare,python,pddlpy --dry-run   # canned, no key
$P grade maintenance my-answer.txt                  # grade by hand
```

Results go to `results/<stamp>/` (gitignored): `results.md` (pass table + run
list), `results.jsonl`, and one transcript per run, with reasoning, code and
PDDL inline. Offline tests: `uv run --with mcp,httpx pytest e2e/llm`.

| Scenario | Optimum | What makes it hard |
|---|---|---|
| `courier` | 7 | nothing: a control case |
| `courier-parcels` | 27 | pickup-and-delivery routing over 28 one-way tolls |
| `blocksworld` | 18 | 8 blocks; tearing everything down works but isn't optimal |
| `mystery-blocksworld` | 16 | same physics with meaningless names (PlanBench) |
| `logistics` | 25 | truck/plane hand-offs across 3 cities |
| `maintenance` | 2 | set cover; the greedy pick leads to 3 days |

**Adding a scenario:** create a directory with `problem.md`, `domain.pddl`,
`problem.pddl` and `meta.json` (`optimal_cost`, `planner`, `source`), then
check it with `$P check NAME`. Use an optimal planner: `ucs` always, `astar`
only for unit costs where no action reaches two goal atoms at once.

## Courier harness (#106) Reproduces
[docs/llm-interaction.md](../../docs/llm-interaction.md) with a *real* model:
the LLM gets the courier problem in natural language plus tools (a local
`write_file` and the pddlpy MCP tools `validate`/`ground`/`solve`/`parse`,
served by `uvx --from "pddlpy[mcp]" pddlpy-mcp` — the published package in a
transient environment). Each run captures a markdown transcript under
`transcripts/` and checks soundness: `validate` was used, `solve` returned the
7-toll optimum, and the final answer narrates it.

## Small / open models — OpenRouter

```bash
export OPENROUTER_API_KEY=...
make e2e-llm MODEL=qwen/qwen-2.5-72b-instruct
# equivalently:
uv run --with mcp,httpx python e2e/llm/harness.py --model qwen/qwen-2.5-72b-instruct
```

Exit codes: `0` sound, `1` finished but unsound (read the transcript), `2`
setup error. No key at hand? `--dry-run` replays the doc's scripted turns
through the entire pipeline (MCP server, tool dispatch, transcript,
soundness) without any API call.

## Mid-tier models — CLI agents

For models we reach through coding agents rather than raw APIs, drive the
same MCP server through the agent's own harness:

```bash
./e2e/llm/claude_driver.sh          # Claude Code: claude -p + --mcp-config
# codex exec works analogously with its MCP configuration
```

The driver prints where it saved the transcript; judge soundness with the
same criteria (validate used, cost 7.0, route narrated).

## Observed results

| Model | Rounds | Outcome |
|---|---|---|
| `qwen/qwen-2.5-72b-instruct` | 2 | R1 **unsound** (double-escaped newlines, invented `:cost` syntax → harness hardened). R2 **sound**: wrote clean PDDL, recovered from a real `solve` rejection (missing `:typing`), narrated the optimum — now the transcript in `docs/llm-interaction.md`. |
| `meta-llama/llama-3.1-8b-instruct` | 3 | All **unsound**, each differently: mangled the map + drifted into pseudo-code instead of tool calls; emitted malformed JSON tool arguments (now answered with an error result instead of crashing); fired 7 tool calls in one batch without reading any result. |

The gap is the point: the 72B model *uses* the fix loop, the 8B model can't
drive it — and the soundness gate correctly refused every unsound round.
Below ~8B, the missing skill isn't PDDL, it's sustained tool use.

## Iterating (issue steps 5–8)

Repeat runs (vary model / round) until a transcript is sound *and reads
well*; then replace the simulated conversation in `docs/llm-interaction.md`
with that transcript (label it with model + date, and turn the "what is
simulated" box into "how this was captured"). Transcripts are gitignored —
commit only the winning one alongside the doc update.
