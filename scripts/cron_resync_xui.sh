#!/usr/bin/env bash
# Weekly maintenance: resync xui clients from DB to panels and reload xray.
#
# What it does:
#   1. Copies the latest resync_xui_clients.py into vpn_hub_bot container.
#   2. Runs the script with --apply for VLESS xui servers (1=NL, 3=FI).
#   3. Restarts x-ui on FI and NL so xray re-reads config.json from x-ui.db.
#
# Why: x-ui (sanaei build) sometimes leaves clients in /etc/x-ui/x-ui.db
# without rendering them into /usr/local/x-ui/bin/config.json, so xray
# doesn't see them and users can't connect. A weekly restart guarantees
# config.json is in sync with x-ui.db.
#
# Designed to run from prod (vpnhub-prod) as user `control` via cron.

set -uo pipefail

REPO="/home/control/vpnhub"
SCRIPT_LOCAL="$REPO/scripts/resync_xui_clients.py"
SCRIPT_IN_CONTAINER="/app/resync_xui_clients.py"
LOG_FILE="$HOME/cron-logs/resync_xui.log"
TS() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }

mkdir -p "$(dirname "$LOG_FILE")"
{
    echo "=================================================="
    echo "[$(TS)] cron_resync_xui start"

    if [ ! -f "$SCRIPT_LOCAL" ]; then
        echo "[$(TS)] ERROR: $SCRIPT_LOCAL not found"
        exit 1
    fi

    echo "[$(TS)] copying script into vpn_hub_bot"
    docker cp "$SCRIPT_LOCAL" "vpn_hub_bot:$SCRIPT_IN_CONTAINER"

    echo "[$(TS)] running --apply --server 1 --server 3"
    docker exec vpn_hub_bot python "$SCRIPT_IN_CONTAINER" \
        --server 1 --server 3 --apply
    rc=$?
    echo "[$(TS)] script exit=$rc"

    for host in 65.108.91.192 206.251.51.225; do
        echo "[$(TS)] restarting x-ui on $host"
        ssh -o BatchMode=yes -o ConnectTimeout=10 "root@$host" \
            'systemctl restart x-ui && sleep 2 && systemctl is-active x-ui'
        echo "[$(TS)] $host restart rc=$?"
    done

    echo "[$(TS)] cron_resync_xui done"
} >> "$LOG_FILE" 2>&1
