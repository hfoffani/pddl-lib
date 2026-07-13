#!/bin/sh
# Mid-tier driver (#106): let Claude Code solve the courier problem through
# the pddlpy MCP server. Requires the `claude` CLI. Manual — not CI.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$HERE/transcripts/claude-$STAMP.md"
MCPCFG=$(mktemp)
trap 'rm -f "$MCPCFG"' EXIT

cat > "$MCPCFG" <<'EOF'
{"mcpServers": {"pddlpy": {"command": "uvx", "args": ["--from", "pddlpy[mcp]", "pddlpy-mcp"]}}}
EOF

PROMPT='A courier is at the depot and must deliver a parcel to town, spending as
little as possible on tolls. The direct highway costs 10. There is a route
through the junction: 5 to get there, then 6 into town. And there is a
back-road chain: riverside (2), then the old bridge (2), then into town (3).
Roads are one-way. What is the cheapest route?

Do not compute the plan yourself. Translate the problem to PDDL (domain +
problem files with :action-costs and a minimize metric), run the pddlpy
validate tool and fix any issue, run the solve tool with planner "ucs", and
answer in plain language based only on the solver output.'

claude -p "$PROMPT" \
  --mcp-config "$MCPCFG" \
  --allowedTools "Write,mcp__pddlpy__validate,mcp__pddlpy__solve,mcp__pddlpy__parse,mcp__pddlpy__ground" \
  --output-format text | tee "$OUT"

echo
echo "transcript: $OUT"
echo "judge soundness: validate used, solve cost 7.0, route narrated"
