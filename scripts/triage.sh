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
art_dir=".artifacts"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="$2"; shift 2 ;;
    --branch) branch="$2"; shift 2 ;;
    --repo-dir) repo_dir="$2"; shift 2 ;;
    --service) service="$2"; shift 2 ;;
    --artifacts-dir) art_dir="$2"; shift 2 ;;
    *) echo "unknown arg: $1" | mask; exit 7 ;;
  esac
done

if [[ -z "$host" ]]; then
  echo "usage: $0 --host <host> --branch <branch> [--repo-dir /opt/vpnhub]" | mask
  exit 7
fi

mkdir -p "$art_dir"
log_file="$art_dir/triage_logs.txt"
triage_md="$art_dir/triage.md"

ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "cd '$repo_dir' && docker compose logs --tail=1000 $service" > "$log_file" 2>&1 || true

health=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $service" 2>/dev/null || echo "unknown")
restart_count=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "docker inspect --format '{{.RestartCount}}' $service" 2>/dev/null || echo "unknown")
commit=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
ts=$(date '+%Y-%m-%d %H:%M:%S %z')

p0_re='Traceback|Unhandled exception|RuntimeError|ModuleNotFoundError|ImportError|event=runtime.fatal|container unhealthy|restart detected'
p1_re='TelegramConflictError|event=polling.conflict|Failed to fetch updates|ERROR.*aiogram|HTTP [5][0-9]{2}'
p2_re='WARNING|timeout|retry'

p0_tmp="$art_dir/.p0.txt"
p1_tmp="$art_dir/.p1.txt"
p2_tmp="$art_dir/.p2.txt"

grep -Ei "$p0_re" "$log_file" > "$p0_tmp" || true
grep -Ei "$p1_re" "$log_file" > "$p1_tmp" || true
grep -Ei "$p2_re" "$log_file" > "$p2_tmp" || true

if [[ "$health" != "healthy" ]]; then
  echo "container unhealthy" >> "$p0_tmp"
fi
if [[ "$restart_count" =~ ^[0-9]+$ ]] && (( restart_count > 0 )); then
  echo "restart detected" >> "$p0_tmp"
fi

p0_count=$(wc -l < "$p0_tmp" | tr -d ' ')
p1_count=$(wc -l < "$p1_tmp" | tr -d ' ')
p2_count=$(wc -l < "$p2_tmp" | tr -d ' ')

{
  echo "# Triage Report"
  echo
  echo "- timestamp: $ts"
  echo "- branch: ${branch:-unknown}"
  echo "- commit: $commit"
  echo "- host: $host"
  echo "- health: $health"
  echo "- restart_count: $restart_count"
  echo "- severity_counts: P0=$p0_count P1=$p1_count P2=$p2_count"
  echo
  echo "## Unique Error Signatures"
  echo
  echo "### P0"
  if [[ -s "$p0_tmp" ]]; then
    awk '{print $0}' "$p0_tmp" | sed 's/^[[:space:]]*//' | sort | uniq -c | sort -nr | head -n 100
  else
    echo "none"
  fi
  echo
  echo "### P1"
  if [[ -s "$p1_tmp" ]]; then
    awk '{print $0}' "$p1_tmp" | sed 's/^[[:space:]]*//' | sort | uniq -c | sort -nr | head -n 100
  else
    echo "none"
  fi
  echo
  echo "## Context (first 20 lines each)"
  echo
  echo "### P0 Context"
  if [[ -s "$p0_tmp" ]]; then
    awk '!seen[$0]++{print $0}' "$p0_tmp" | head -n 20
  else
    echo "none"
  fi
  echo
  echo "### P1 Context"
  if [[ -s "$p1_tmp" ]]; then
    awk '!seen[$0]++{print $0}' "$p1_tmp" | head -n 20
  else
    echo "none"
  fi
} | mask > "$triage_md"

if (( p0_count > 0 || p1_count > 0 )); then
  echo "triage: P0/P1 found" | mask
  exit 7
fi

echo "triage: ok" | mask
exit 0
