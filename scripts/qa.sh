#!/usr/bin/env bash
set -euo pipefail

mask() {
  sed -E \
    -e 's#bot[0-9]{6,}:[A-Za-z0-9_-]{20,}#***REDACTED***#g' \
    -e 's#(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]]+#\1=***REDACTED***#g' \
    -e 's#(CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*([:=])[[:space:]]*[^[:space:]]+#\1\2***REDACTED***#gI' \
    -e 's#-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----#***REDACTED***#g'
}

fail=0

if ! python3 -m compileall bot/bot 2>&1 | mask; then
  fail=1
fi

if [[ -f scripts/qa/check_callbacks.py ]]; then
  if ! python3 scripts/qa/check_callbacks.py --root bot/bot 2>&1 | mask; then
    fail=1
  fi
fi

if [[ -d tests ]]; then
  if ! pytest -q 2>&1 | mask; then
    fail=1
  fi
fi

legacy_service_imports="$(rg -n "from bot\\.service\\.|import bot\\.service\\.|bot\\.service\\." bot tests || true)"
if [[ -n "${legacy_service_imports}" ]]; then
  printf '%s\n' "$legacy_service_imports" | mask
  echo "qa: legacy bot.service imports detected" | mask
  fail=1
fi

legacy_payment_helper_imports="$(rg -n "from bot\\.handlers\\.payment_webhook|import bot\\.handlers\\.payment_webhook|bot\\.handlers\\.payment_webhook" bot tests docs/runbook.md || true)"
if [[ -n "${legacy_payment_helper_imports}" ]]; then
  printf '%s\n' "$legacy_payment_helper_imports" | mask
  echo "qa: legacy bot.handlers.payment_webhook imports detected" | mask
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "qa: failed" | mask
  exit 4
fi

echo "qa: ok" | mask
exit 0
