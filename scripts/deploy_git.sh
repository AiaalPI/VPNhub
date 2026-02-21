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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) host="$2"; shift 2 ;;
    --branch) branch="$2"; shift 2 ;;
    --repo-dir) repo_dir="$2"; shift 2 ;;
    *) echo "unknown arg: $1" | mask; exit 5 ;;
  esac
done

if [[ -z "$host" || -z "$branch" ]]; then
  echo "usage: $0 --host <host> --branch <branch> [--repo-dir /opt/vpnhub]" | mask
  exit 5
fi

if ! out=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "$host" "bash -s" <<EOSSH
set -euo pipefail
cd "$repo_dir"
test -d "$repo_dir"
test -f docker-compose.yml
git fetch --all --prune
git checkout "$branch"
git reset --hard "origin/$branch"
docker compose build --no-cache vpn_hub_bot
docker compose up -d vpn_hub_bot
docker compose ps
EOSSH
); then
  echo "deploy: failed" | mask
  exit 5
fi

echo "$out" | mask
echo "deploy: ok" | mask
exit 0
