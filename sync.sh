#!/usr/bin/env bash
# Sync the canonical gen_media.py from shared/ into both skill folders.
# Run after editing shared/gen_media.py. Maintainer-only; end users never run this.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/shared/gen_media.py"
if [ ! -f "$SRC" ]; then
  echo "ERROR: $SRC not found" >&2
  exit 1
fi
for skill in gen-image gen-video; do
  DST="$ROOT/plugins/gen-media/skills/$skill/scripts/gen_media.py"
  cp "$SRC" "$DST"
  echo "synced → $skill/scripts/gen_media.py"
done
