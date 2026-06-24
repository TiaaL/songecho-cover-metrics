#!/usr/bin/env bash
set -euo pipefail

AUDIO_DIR="${1:-audio}"
OUT_DIR="${2:-separated}"

mkdir -p "$OUT_DIR"

find "$AUDIO_DIR" -maxdepth 1 -type f \( \
  -iname '*.wav' -o -iname '*.mp3' -o -iname '*.flac' -o -iname '*.m4a' \
\) -print0 | sort -z | while IFS= read -r -d '' audio; do
  python -m demucs -n htdemucs_ft --two-stems vocals -o "$OUT_DIR" "$audio"
done
