#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

redact() {
  sed -E \
    -e 's/(bot[0-9]{6,}:[A-Za-z0-9_-]{20,})/***REDACTED***/g' \
    -e 's/(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN|YOOKASSA_SECRET_KEY|CRYPTOMUS_KEY|PASSWORD)[^[:space:]]*/\\1=***REDACTED***/g'
}

log() { echo "event=release_train.daily $*"; }

log "step=qa.start"
./scripts/release_train/release_build.sh 2>&1 | redact
log "step=qa.done"

log "step=signals.hint msg='Check prod logs/metrics and open issues for regressions'"
log "next=run_post_release_check cmd=./scripts/release_train/post_release_check.sh"

