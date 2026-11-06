#!/usr/bin/env bash
# Called only by GitHub Actions through /opt/vpnhub/deploy.sh bridge.
set -euo pipefail
[[ $# == 0 ]] || { echo 'No bridge arguments accepted' >&2; exit 2; }
[[ $EUID == 0 ]] || { echo 'Bridge deployment requires root' >&2; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v haproxy >/dev/null
haproxy -c -f "$ROOT/configs/bridge/haproxy.cfg"

# Fail before changing service state if the fixed upstream route is unavailable.
python3 - <<'PY'
import socket
for port in (443, 2087):
    with socket.create_connection(('2605:e440:7::1:1a8', port), timeout=5):
        pass
PY

backup="/root/vpnhub-backups/bridge-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
config=/etc/vpnhub/bridge.cfg
unit=/etc/systemd/system/vpnhub-bridge.service
had_config=false
had_unit=false
was_active=false
was_enabled=false
if [[ -f "$config" ]]; then cp -p "$config" "$backup/config"; had_config=true; fi
if [[ -f "$unit" ]]; then cp -p "$unit" "$backup/unit"; had_unit=true; fi
systemctl is-active --quiet vpnhub-bridge && was_active=true
systemctl is-enabled --quiet vpnhub-bridge && was_enabled=true

restore_on_error() {
    local status=$?
    trap - ERR
    set +e
    systemctl stop vpnhub-bridge
    if "$had_config"; then cp -p "$backup/config" "$config"; else rm -f "$config"; fi
    if "$had_unit"; then cp -p "$backup/unit" "$unit"; else rm -f "$unit"; fi
    systemctl daemon-reload
    if "$had_unit"; then
        if "$was_enabled"; then systemctl enable vpnhub-bridge; else systemctl disable vpnhub-bridge; fi
        "$was_active" && systemctl start vpnhub-bridge
    else
        systemctl disable vpnhub-bridge 2>/dev/null
    fi
    echo "Bridge deployment failed; previous files restored from $backup" >&2
    exit "$status"
}
trap restore_on_error ERR
install -d -m 755 /etc/vpnhub
install -m 644 "$ROOT/configs/bridge/haproxy.cfg" "$config"
install -m 644 "$ROOT/configs/bridge/vpnhub-bridge.service" "$unit"
systemctl daemon-reload
systemctl enable vpnhub-bridge
systemctl restart vpnhub-bridge
sleep 1
systemctl is-active --quiet vpnhub-bridge
python3 - <<'PY'
import socket
for port in (443, 2087):
    with socket.create_connection(('89.125.136.14', port), timeout=5):
        pass
PY
trap - ERR
echo "Bridge service active; rollback files: $backup"
echo 'A full external VPN probe is still required; TCP checks do not prove VPN access.'
