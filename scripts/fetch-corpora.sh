#!/usr/bin/env bash
# Fetch the full IPC benchmark corpora at pinned commits (#153).
#
# The corpora stay out of the repo: they land in a git-ignored directory
# (default .corpora/, override with CORPORA_DIR). Used by the oracle CI
# workflow and for opt-in local runs. Re-running is a no-op once a corpus
# is at its pinned commit.
#
#   scripts/fetch-corpora.sh            # all corpora
#   scripts/fetch-corpora.sh potassco   # one corpus
set -euo pipefail

DEST="${CORPORA_DIR:-.corpora}"

# name  url  pinned-commit
CORPORA="
potassco https://github.com/potassco/pddl-instances.git cf19edf7c53d1540ddbb396c642595e0926ee552
classical https://github.com/AI-Planning/classical-domains.git 4bd0b42d89ea02bd38af6f93cf20a0ab0cbda9d9
"

fetch() {
  local name="$1" url="$2" commit="$3" dir="$DEST/$1"
  if [ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" = "$commit" ]; then
    echo "$name: already at $commit"
    return
  fi
  mkdir -p "$dir"
  git -C "$dir" init -q
  git -C "$dir" fetch -q --depth 1 "$url" "$commit"
  git -C "$dir" checkout -q --detach FETCH_HEAD
  echo "$name: $commit"
}

found=0
while read -r name url commit; do
  [ -z "$name" ] && continue
  if [ $# -eq 0 ] || [ "$1" = "$name" ]; then
    fetch "$name" "$url" "$commit"
    found=1
  fi
done <<< "$CORPORA"

if [ "$found" = 0 ]; then
  echo "unknown corpus: $1" >&2
  exit 2
fi
