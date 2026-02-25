#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

redact() {
  sed -E \
    -e 's/(bot[0-9]{6,}:[A-Za-z0-9_-]{20,})/***REDACTED***/g' \
    -e 's/(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN|YOOKASSA_SECRET_KEY|CRYPTOMUS_KEY|PASSWORD)[^[:space:]]*/\\1=***REDACTED***/g'
}

log() { echo "event=release_train.post_release $*"; }

log "step=ps"
docker compose ps 2>&1 | redact

log "step=health"
curl -fsS http://127.0.0.1:8888/health 2>/dev/null || true

log "step=errors_scan"
docker logs --tail=200 vpn_hub_bot 2>&1 | egrep -i "TelegramUnauthorizedError|TelegramConflictError|ConflictError|Traceback|ERROR|event=runtime.fatal" || true

log "status=ok note='If /health not implemented yet, curl may fail (expected until Sprint 1 ships)'."

