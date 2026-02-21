#!/usr/bin/env bash
set -euo pipefail

# This script must be executed on server as user "deployer".
# "deployer" should be a member of docker group and have access to /opt/vpnhub.

cd /opt/vpnhub

git fetch origin
git reset --hard origin/main

docker compose build vpn_hub_bot
docker compose up -d vpn_hub_bot

docker compose ps
docker compose logs --tail=120 vpn_hub_bot || true
