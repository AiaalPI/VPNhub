#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

VERSION="${1:-}"
OUT="${2:-.artifacts/release_notes.md}"

mkdir -p "$(dirname "$OUT")"

log() { echo "event=release_train.release_notes $*"; }

if [ -z "$VERSION" ]; then
  log "status=error reason=missing_version"
  echo "Usage: $0 <version> [output_path]" >&2
  exit 2
fi

last_tag="$(git tag --list 'v*' --sort=-version:refname | head -n 1 || true)"

{
  echo "# Release Notes — v${VERSION}"
  echo
  echo "## Summary"
  echo "- TODO"
  echo
  echo "## Changes"
  if [ -n "$last_tag" ]; then
    echo
    echo "Since ${last_tag}:"
    git log --no-merges --pretty='- %s (%h)' "${last_tag}..HEAD"
  else
    echo
    echo "Initial notes (no previous tags found):"
    git log --no-merges --pretty='- %s (%h)' HEAD~50..HEAD 2>/dev/null || git log --no-merges --pretty='- %s (%h)'
  fi
  echo
  echo "## Verification"
  echo "- Build: \`docker compose build vpn_hub_bot\`"
  echo "- Smoke: \`./scripts/release_train/post_release_check.sh\`"
} > "$OUT"

log "status=ok out=$OUT"

