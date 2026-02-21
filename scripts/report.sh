#!/usr/bin/env bash
set -euo pipefail

mask() {
  sed -E \
    -e 's#bot[0-9]{6,}:[A-Za-z0-9_-]{20,}#***REDACTED***#g' \
    -e 's#(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]]+#\1=***REDACTED***#g' \
    -e 's#(CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*([:=])[[:space:]]*[^[:space:]]+#\1\2***REDACTED***#gI' \
    -e 's#-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----#***REDACTED***#g'
}

status="FAIL"
branch="$(git branch --show-current 2>/dev/null || echo unknown)"
commit="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
host="${HOST:-unknown}"
health="unknown"
restart_count="unknown"
p0_count="0"
p1_count="0"
taskpack_path="${TASKPACK_PATH:-none}"

mkdir -p .artifacts

if [[ -f .artifacts/triage.md ]]; then
  health=$(grep -E '^- health:' .artifacts/triage.md | head -n1 | awk -F': ' '{print $2}')
  restart_count=$(grep -E '^- restart_count:' .artifacts/triage.md | head -n1 | awk -F': ' '{print $2}')
  sev=$(grep -E '^- severity_counts:' .artifacts/triage.md | head -n1 || true)
  p0_count=$(echo "$sev" | sed -E 's/.*P0=([0-9]+).*/\1/' )
  p1_count=$(echo "$sev" | sed -E 's/.*P1=([0-9]+).*/\1/' )
fi

if [[ "${PIPELINE_OK:-0}" == "1" ]]; then
  status="PASS"
fi

cat > .artifacts/report.md <<EOR
# Orchestrator V3 Report

- STATUS: $status
- Branch: $branch
- Commit: $commit
- Host: $host
- Health: ${health:-unknown}
- Restart count: ${restart_count:-unknown}
- P0 count: ${p0_count:-0}
- P1 count: ${p1_count:-0}
- Taskpack path: $taskpack_path

## Rollback Instructions
1. git log --oneline -n 20
2. git checkout <previous_commit>
3. docker compose up -d --build vpn_hub_bot

Warning: do not delete DB volumes.
EOR

cat .artifacts/report.md | mask
