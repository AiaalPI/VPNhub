#!/usr/bin/env bash
set -euo pipefail

mask() {
  sed -E \
    -e 's#bot[0-9]{6,}:[A-Za-z0-9_-]{20,}#***REDACTED***#g' \
    -e 's#(TG_TOKEN|BOT_TOKEN|TELEGRAM_BOT_TOKEN|YOOMONEY_TOKEN)[[:space:]]*=[[:space:]]*[^[:space:]]+#\1=***REDACTED***#g' \
    -e 's#(CRYPTOMUS|YOOKASSA|SECRET|PASSWORD)[[:space:]]*([:=])[[:space:]]*[^[:space:]]+#\1\2***REDACTED***#gI' \
    -e 's#-----BEGIN (RSA|OPENSSH) PRIVATE KEY-----#***REDACTED***#g'
}

host=""
branch=""
repo_dir="/opt/vpnhub"
service="vpn_hub_bot"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="$2"; shift 2 ;;
    --branch) branch="$2"; shift 2 ;;
    --repo-dir) repo_dir="$2"; shift 2 ;;
    --service) service="$2"; shift 2 ;;
    *) echo "unknown arg: $1" | mask; exit 1 ;;
  esac
done

if [[ -z "$host" ]]; then
  echo "usage: $0 --host <host> [--branch <branch>] [--repo-dir /opt/vpnhub]" | mask
  exit 1
fi

if [[ -z "$branch" ]]; then
  branch=$(git branch --show-current)
fi

mkdir -p .artifacts
export HOST="$host"
PIPELINE_OK=0
TASKPACK_PATH="none"

# Step 0: Git Clean Guard
if [[ -n "$(git status --porcelain)" ]]; then
  echo "gate: git working tree is not clean" | mask
  exit 3
fi

# Step 1: Preflight
if ! ./scripts/preflight.sh; then
  ./scripts/report.sh || true
  exit 2
fi

# Step 2: QA
if ! ./scripts/qa.sh; then
  ./scripts/report.sh || true
  exit 4
fi

# Step 3: Commit + Push branch (sync only)
git fetch --all --prune >/dev/null 2>&1 || true
git push origin "$branch" 2>&1 | mask

# Step 4: Deploy
if ! ./scripts/deploy_git.sh --host "$host" --branch "$branch" --repo-dir "$repo_dir"; then
  ./scripts/triage.sh --host "$host" --branch "$branch" --repo-dir "$repo_dir" --service "$service" || true
  TASKPACK_PATH=$(./scripts/handoff.sh --branch "$branch" --triage-file .artifacts/triage.md | tail -n1)
  export TASKPACK_PATH
  ./scripts/report.sh || true
  exit 5
fi

# Step 5: Smoke
smoke_code=0
./scripts/smoke.sh --host "$host" --repo-dir "$repo_dir" --service "$service" || smoke_code=$?

# Step 6: Triage
triage_code=0
./scripts/triage.sh --host "$host" --branch "$branch" --repo-dir "$repo_dir" --service "$service" || triage_code=$?

# Step 7: Hard gates
if [[ "$smoke_code" -ne 0 || "$triage_code" -ne 0 ]]; then
  TASKPACK_PATH=$(./scripts/handoff.sh --branch "$branch" --triage-file .artifacts/triage.md | tail -n1)
  export TASKPACK_PATH
  ./scripts/report.sh || true
  if [[ "$smoke_code" -ne 0 ]]; then
    exit "$smoke_code"
  fi
  exit "$triage_code"
fi

# Step 8: Final report
PIPELINE_OK=1
export PIPELINE_OK
export TASKPACK_PATH
./scripts/report.sh

echo "orchestrator_v3: PASS" | mask
exit 0
