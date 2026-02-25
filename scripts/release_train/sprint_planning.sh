#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DRY_RUN="${DRY_RUN:-1}"
SPRINT="${1:-Sprint 1}"

log() { echo "event=release_train.sprint_planning $*"; }

need_gh() {
  if ! command -v gh >/dev/null 2>&1; then
    log "status=blocked reason=gh_not_installed"
    echo "Install GitHub CLI: https://cli.github.com/ ; then: gh auth login" >&2
    exit 2
  fi
}

run() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "+ $*"
  else
    eval "$@"
  fi
}

need_gh

log "mode=$( [ \"$DRY_RUN\" = \"1\" ] && echo dry_run || echo apply ) sprint=\"$SPRINT\""

# Labels (idempotent; gh returns non-zero if exists)
labels=(
  "P0" "P1" "P2"
  "epic" "infra" "growth" "china" "failover" "ux" "ai-agent"
  "bug" "tech-debt" "release-train"
)

for l in "${labels[@]}"; do
  run "gh label create \"$l\" --force --description \"\" >/dev/null 2>&1 || true"
done

# Milestones (create if missing)
run "gh api -X POST repos/{owner}/{repo}/milestones -f title=\"$SPRINT\" >/dev/null 2>&1 || true"

# Sprint 1 issues (focus list)
create_issue() {
  local title="$1"
  local labels_csv="$2"
  local body="$3"
  run "gh issue create --title \"$title\" --label \"$labels_csv\" --milestone \"$SPRINT\" --body \"$body\""
}

create_issue \
  "P0: Add FastAPI /health endpoint + switch compose healthcheck" \
  "P0,infra,observability,release-train" \
  $'Why: make health deterministic; unblock safe deploy/monitoring.\n\nTasks:\n- [ ] Add GET /health in bot/bot/webhooks/base.py (DB quick check)\n- [ ] Switch docker-compose.yml healthcheck from /docs to /health\n- [ ] Add docs: how to verify health\n\nAcceptance:\n- curl -fsS http://127.0.0.1:8888/health returns JSON {status:\"ok\"}\n- docker inspect vpn_hub_bot shows Health=healthy'

create_issue \
  "P0: Structured error signatures + log triage gate" \
  "P0,infra,observability,release-train" \
  $'Why: prevent silent regressions and accelerate incident response.\n\nTasks:\n- [ ] Ensure critical failures log event=runtime.fatal\n- [ ] Add/extend scripts/triage.sh classification for bot\n- [ ] Document grep commands for TelegramUnauthorized/Conflict/Traceback\n\nAcceptance:\n- triage output contains dedup signatures\n- CI/ops workflow blocks on P0/P1 signatures'

create_issue \
  "P1: China smoke test runbook + monthly execution checklist" \
  "P1,china,infra" \
  $'Why: CN networks fail differently; need deterministic check to avoid blind rollout.\n\nTasks:\n- [ ] Add docs/ai-release-train check: CN smoke run via CN VPS/proxy\n- [ ] Define success criteria (protocol fallback path)\n\nAcceptance:\n- Documented steps runnable by ops\n- Results recorded per month'

create_issue \
  "P1: Auto-failover MVP spec + implementation plan (no refactor)" \
  "P1,failover,infra" \
  $'Why: server degradation directly impacts retention and churn.\n\nTasks:\n- [ ] Define health scoring inputs (latency/error rate)\n- [ ] Define exclusion + reinclude cooldown\n- [ ] Define user reassignment UX (Back/Main menu recovery)\n\nAcceptance:\n- Spec includes file-level implementation plan and verification commands'

log "status=ok next='Set up GitHub Project columns manually or via gh project (optional)'"

