#!/usr/bin/env bash
set -euo pipefail

# This script must be executed on server as user "deployer".
# "deployer" should be a member of docker group and have access to /opt/vpnhub.

cd /opt/vpnhub

git fetch origin
git reset --hard origin/main

msgfmt bot/bot/locale/ru/LC_MESSAGES/bot.po -o bot/bot/locale/ru/LC_MESSAGES/bot.mo
msgfmt bot/bot/locale/en/LC_MESSAGES/bot.po -o bot/bot/locale/en/LC_MESSAGES/bot.mo

docker compose build vpn_hub_bot
docker compose stop vpn_hub_bot || true
sleep 10
docker compose rm -f vpn_hub_bot || true
docker compose up -d vpn_hub_bot

docker compose ps
docker compose logs --tail=120 vpn_hub_bot || true
