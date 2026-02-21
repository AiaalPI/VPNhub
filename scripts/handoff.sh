#!/usr/bin/env bash
set -euo pipefail

mask() {
  sed -E \
    -e 's#bot[0-9]{6,}:[A-Za-z0-9_-]{20,}#***REDACTED***#g' \
    -e 's#(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]]+#\1=***REDACTED***#g' \
    -e 's#(CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*([:=])[[:space:]]*[^[:space:]]+#\1\2***REDACTED***#gI' \
    -e 's#-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----#***REDACTED***#g'
}

branch=""
triage_file=".artifacts/triage.md"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) branch="$2"; shift 2 ;;
    --triage-file) triage_file="$2"; shift 2 ;;
    *) echo "unknown arg: $1" | mask; exit 1 ;;
  esac
done

if [[ -z "$branch" ]]; then
  branch=$(git branch --show-current 2>/dev/null || echo "unknown")
fi

ts=$(date '+%Y%m%d-%H%M')
out_dir="docs/ops/taskpacks/${ts}-${branch}"
mkdir -p "$out_dir"

if [[ -f "$triage_file" ]]; then
  evidence=$(sed -n '1,120p' "$triage_file" | mask)
else
  evidence="No triage evidence file found."
fi

write_pack() {
  local file="$1"
  local role="$2"
  cat > "$file" <<EOT
# ${role}

## Context
- Branch: ${branch}
- Generated: $(date '+%Y-%m-%d %H:%M:%S %z')
- Pipeline: Orchestrator V3

## Evidence (redacted)

evidence

## Suspected Root Cause
- Inspect P0/P1 signatures and map to deploy/runtime/config root cause.

## Minimal Fix Strategy
- Propose smallest safe patch.
- Do not change business logic.
- Verify with smoke + triage gates.

## Exact Commands
- \
  docker compose ps
- \
  docker compose logs --tail=300 vpn_hub_bot
- \
  curl -fsS http://127.0.0.1:8888/health

## Ready-to-paste Prompt (${role})
"Act as ${role}. Use the evidence below and provide the minimal safe fix to clear P0/P1 and pass smoke gates."
EOT

  python3 - <<PY
from pathlib import Path
p = Path(${file@Q})
t = p.read_text(encoding='utf-8')
evidence = ${evidence@Q}
p.write_text(t.replace('evidence', evidence, 1), encoding='utf-8')
PY
}

write_pack "$out_dir/00_summary.md" "Summary"
write_pack "$out_dir/01_planner.md" "Planner"
write_pack "$out_dir/02_coder.md" "Coder"
write_pack "$out_dir/03_qa.md" "QA"
write_pack "$out_dir/04_devops.md" "DevOps"
write_pack "$out_dir/05_security.md" "Security"

echo "$out_dir" | mask
