#!/usr/bin/env bash
set -euo pipefail

mask() {
  sed -E \
    -e 's#bot[0-9]{6,}:[A-Za-z0-9_-]{20,}#***REDACTED***#g' \
    -e 's#(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]]+#\1=***REDACTED***#g' \
    -e 's#(CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*([:=])[[:space:]]*[^[:space:]]+#\1\2***REDACTED***#gI' \
    -e 's#-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----#***REDACTED***#g'
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: not a git repository" | mask
  exit 1
fi

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml not found" | mask
  exit 1
fi

if git ls-files --error-unmatch bot/.env >/dev/null 2>&1; then
  echo "ERROR: bot/.env is tracked by git" | mask
  exit 2
fi

secret_re='bot[0-9]{6,}:[A-Za-z0-9_-]{20,}|(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=|((CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*[:=][[:space:]]*[^[:space:]]+)|BEGIN (RSA|OPENSSH) PRIVATE KEY'

hits_file=".artifacts/preflight_secrets.txt"
mkdir -p .artifacts
: > "$hits_file"

while IFS= read -r -d '' f; do
  if grep -nIE "$secret_re" "$f" >> "$hits_file" 2>/dev/null; then
    true
  fi
done < <(git ls-files -z)

if [[ -s "$hits_file" ]]; then
  echo "ERROR: potential secrets found in tracked files:" | mask
  cat "$hits_file" | mask
  exit 2
fi

# --- Dependency vulnerability scan ---
if command -v pip-audit >/dev/null 2>&1; then
  echo "preflight: running pip-audit..." | mask
  audit_file=".artifacts/preflight_audit.txt"
  if pip-audit -r bot/requirements.txt --desc --progress-spinner off > "$audit_file" 2>&1; then
    echo "preflight: pip-audit ok (0 vulnerabilities)" | mask
  else
    echo "WARNING: pip-audit found vulnerabilities:" | mask
    cat "$audit_file" | mask
  fi
else
  echo "preflight: pip-audit not installed, skipping vulnerability scan" | mask
fi

echo "preflight: ok" | mask
exit 0
