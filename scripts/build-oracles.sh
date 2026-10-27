#!/usr/bin/env bash
# Fetch and build the external oracles at pinned commits (#153):
# Fast Downward (GPL-3.0, run as a subprocess only, never vendored), VAL
# (BSD-3-Clause) and INVAL (needs SBCL).
#
# Everything lands in ORACLES_DIR (default .oracles/, git-ignored), so it
# can live on an external disk. Re-running skips what is already built.
#
#   scripts/build-oracles.sh             # all oracles
#   scripts/build-oracles.sh VAL         # one oracle
#
# Needs git, cmake, a C++ compiler and Python 3 (FD, VAL), and sbcl (INVAL).
set -euo pipefail

DEST="${ORACLES_DIR:-.oracles}"

# name  url  pinned-commit
ORACLES="
downward https://github.com/aibasel/downward.git 7ea2755269ff9398279b30f5c848e32ba6047c9c
VAL https://github.com/KCL-Planning/VAL.git 3c7a1f330bdab0ba28a4762bb45c3f06c27fb6d4
INVAL https://github.com/patrikhaslum/INVAL.git 24088ca1ccd25a1f8f4b5cd57cc0c0e34c081f6d
"

fetch() {
  local url="$1" commit="$2" dir="$3"
  if [ "$(git -C "$dir" rev-parse HEAD 2>/dev/null)" = "$commit" ]; then
    return
  fi
  mkdir -p "$dir"
  git -C "$dir" init -q
  git -C "$dir" fetch -q --depth 1 "$url" "$commit"
  git -C "$dir" checkout -q --detach FETCH_HEAD
}

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JOBS="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"

# Binaries, as tests/oracles.py expects them under ORACLES_DIR:
#   downward/fast-downward.py, VAL/build/bin/Validate, INVAL/inval
build() {
  local name="$1" dir="$2"
  case "$name" in
    downward)
      [ -x "$dir/builds/release/bin/downward" ] && return
      (cd "$dir" && python3 build.py release -j "$JOBS") ;;
    VAL)
      [ -x "$dir/build/bin/Validate" ] && return
      # VAL declares cmake_minimum_required(VERSION 2.8); CMake 4 refuses
      # anything below 3.5 unless told the policy floor explicitly.
      cmake -S "$dir" -B "$dir/build" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5
      cmake --build "$dir/build" --target Validate -j "$JOBS" ;;
    INVAL)
      [ -x "$dir/inval" ] && return
      cp "$HERE/inval-sbcl.lsp" "$dir/"
      (cd "$dir" && sbcl --non-interactive --load inval-sbcl.lsp) ;;
  esac
}

found=0
while read -r name url commit; do
  [ -z "$name" ] && continue
  if [ $# -eq 0 ] || [ "$1" = "$name" ]; then
    fetch "$url" "$commit" "$DEST/$name"
    build "$name" "$DEST/$name"
    echo "$name: $commit"
    found=1
  fi
done <<< "$ORACLES"

if [ "$found" = 0 ]; then
  echo "unknown oracle: $1" >&2
  exit 2
fi
