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

if [[ "$fail" -ne 0 ]]; then
  echo "qa: failed" | mask
  exit 4
fi

echo "qa: ok" | mask
exit 0
