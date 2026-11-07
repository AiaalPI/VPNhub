#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "${1:-}" == "bridge" ]]; then
    shift
    exec bash "$ROOT/scripts/deploy_bridge.sh" "$@"
fi
if [[ "${1:-}" == "subscriptions-origin" ]]; then
    shift
    exec bash "$ROOT/scripts/activate_mow2_exports.sh" "$@"
fi

exec "$ROOT/server/deploy.sh"
