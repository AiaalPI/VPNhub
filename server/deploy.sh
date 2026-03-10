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
docker compose stop vpn_hub_bot || true
sleep 10
docker compose rm -f vpn_hub_bot || true
docker compose up -d vpn_hub_bot

docker compose ps
docker compose logs --tail=120 vpn_hub_bot || true
