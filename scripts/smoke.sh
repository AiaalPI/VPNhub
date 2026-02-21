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
repo_dir="/opt/vpnhub"
service="vpn_hub_bot"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="$2"; shift 2 ;;
    --repo-dir) repo_dir="$2"; shift 2 ;;
    --service) service="$2"; shift 2 ;;
    *) echo "unknown arg: $1" | mask; exit 6 ;;
  esac
done

if [[ -z "$host" ]]; then
  echo "usage: $0 --host <host> [--repo-dir /opt/vpnhub] [--service vpn_hub_bot]" | mask
  exit 6
fi

ps_out=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "cd '$repo_dir' && docker compose ps $service" 2>&1 || true)
echo "$ps_out" | mask
if ! echo "$ps_out" | grep -Eq "$service.*(Up|running|healthy)"; then
  echo "smoke: container is not up" | mask
  exit 6
fi

health=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $service" 2>/dev/null || true)
health=$(echo "$health" | tr -d '\r')
if [[ "$health" != "healthy" ]]; then
  echo "smoke: unhealthy status=$health" | mask
  exit 6
fi

restart_count=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "docker inspect --format '{{.RestartCount}}' $service" 2>/dev/null || echo "999")
restart_count=$(echo "$restart_count" | tr -d '\r')
if [[ ! "$restart_count" =~ ^[0-9]+$ ]]; then
  echo "smoke: invalid restart_count=$restart_count" | mask
  exit 6
fi
if (( restart_count > 0 )); then
  echo "smoke: restart count > 0 ($restart_count)" | mask
  exit 6
fi

health_body=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "curl -fsS http://127.0.0.1:8888/health" 2>/dev/null || true)
if ! echo "$health_body" | grep -qi "ok"; then
  echo "smoke: /health did not contain ok" | mask
  exit 6
fi

logs=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "cd '$repo_dir' && docker compose logs --tail=300 $service" 2>&1 || true)
if echo "$logs" | grep -Eiq "TelegramConflictError|Conflict"; then
  echo "smoke: conflict detected" | mask
  exit 2
fi
if echo "$logs" | grep -q "event=runtime.fatal"; then
  echo "smoke: runtime fatal found" | mask
  exit 6
fi

echo "smoke: ok health=$health restart_count=$restart_count" | mask
exit 0
