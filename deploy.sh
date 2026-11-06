#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "bridge" ]]; then
    shift
    exec bash "$ROOT/scripts/deploy_bridge.sh" "$@"
fi

exec "$ROOT/server/deploy.sh"
