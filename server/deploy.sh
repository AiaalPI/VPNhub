#!/usr/bin/env bash
set -euo pipefail

# This script must be executed on server as user "deployer".
# "deployer" should be a member of docker group and have access to /opt/vpnhub.

cd /opt/vpnhub

BRANCH=$(git branch --show-current)
if [ "$BRANCH" != "main" ]; then
  echo "ERROR: Not on main branch! Current: $BRANCH"
  exit 1
fi

# Prevent destructive sync if there are local changes.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: Working tree is dirty. Commit or stash before deploy."
  exit 1
fi

git fetch origin
git pull --ff-only origin main

msgfmt bot/bot/locale/ru/LC_MESSAGES/bot.po -o bot/bot/locale/ru/LC_MESSAGES/bot.mo
msgfmt bot/bot/locale/en/LC_MESSAGES/bot.po -o bot/bot/locale/en/LC_MESSAGES/bot.mo

docker compose build vpn_hub_bot
# Take a database backup before startup runs migrations.
backup_dir=/opt/vpnhub/backups/postgres
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
(umask 077; docker compose exec -T db_postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_dir/predeploy-$(date -u +%Y%m%dT%H%M%SZ).dump")
docker compose stop vpn_hub_bot || true
sleep 10
docker compose rm -f vpn_hub_bot || true
docker compose up -d vpn_hub_bot

docker compose ps
docker compose logs --tail=120 vpn_hub_bot || true

# Opt-in shared-port ingress; activation is an explicit production decision.
if [[ -f /etc/vpnhub/portal-ingress.enabled ]]; then
    ready=false
    for attempt in $(seq 1 60); do
        if curl -fsS http://127.0.0.1:8888/health >/dev/null; then ready=true; break; fi
        sleep 2
    done
    "$ready" || { echo 'Bot is not ready; ingress left unchanged'; exit 1; }
    bash scripts/deploy_portal_ingress.sh
fi
