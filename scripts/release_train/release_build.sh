#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

redact() {
  sed -E \
    -e 's/(bot[0-9]{6,}:[A-Za-z0-9_-]{20,})/***REDACTED***/g' \
    -e 's/(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN|YOOKASSA_SECRET_KEY|CRYPTOMUS_KEY|PASSWORD)[^[:space:]]*/\\1=***REDACTED***/g'
}

log() { echo "event=release_train.build $*"; }

log "step=compileall"
python3 -m compileall -q bot 2>&1 | redact

if [ -d tests ]; then
  log "step=pytest"
  pytest -q 2>&1 | redact
fi

log "step=docker_build service=vpn_hub_bot"
docker compose build vpn_hub_bot 2>&1 | redact

log "status=ok"

