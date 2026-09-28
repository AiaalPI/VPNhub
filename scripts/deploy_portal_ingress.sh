#!/usr/bin/env bash
# Called ONLY by /opt/vpnhub/deploy.sh after a reviewed GitHub Actions deployment.
set -euo pipefail
cd /opt/vpnhub
[[ $EUID == 0 ]] || { echo 'Portal ingress requires root'; exit 1; }
exec 9>/run/vpnhub-portal-ingress.lock
flock -n 9 || exit 1
umask 077
state=/var/lib/vpnhub-portal
mkdir -p "$state" "$state/acme"
chmod 755 "$state/acme"
certs=vpnhub_subscription-certbot-etc
image=nginx:1.27-alpine
# Issue the certificate before touching the VPN listener; reuse the existing ACME account.
if ! docker run --rm -v "$certs:/etc/letsencrypt:ro" --entrypoint sh "$image" -c 'test -s /etc/letsencrypt/live/kynnet.space/fullchain.pem'; then
    docker run -d --name vpnhub-portal-acme --network host \
        -v "$PWD/configs/portal/nginx-acme.conf:/etc/nginx/nginx.conf:ro" \
        -v "$state/acme:/var/www/certbot:ro" "$image"
    trap 'docker rm -f vpnhub-portal-acme >/dev/null 2>&1 || true' EXIT
    docker run --rm --network host -v "$certs:/etc/letsencrypt" \
        -v "$state/acme:/var/www/certbot" certbot/certbot:latest certonly \
        --webroot -w /var/www/certbot --non-interactive --cert-name kynnet.space -d kynnet.space
    docker rm -f vpnhub-portal-acme >/dev/null
    trap - EXIT
fi
args=(--network host --memory 128m --cpus .5
      --log-opt max-size=10m --log-opt max-file=3
      -v "$PWD/configs/portal/nginx-shared.conf:/etc/nginx/nginx.conf:ro"
      -v "$certs:/etc/letsencrypt:ro" -v "$state/acme:/var/www/certbot:ro")
docker run --rm "${args[@]}" "$image" nginx -t
# Keep a consistent SQLite backup; only listener fields are restored on failed bootstrap.
backup="$state/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$backup"
python3 - "$backup/x-ui.db" <<'PY'
import sqlite3,sys
with sqlite3.connect('/etc/x-ui/x-ui.db') as src, sqlite3.connect(sys.argv[1]) as dst:
    src.backup(dst)
PY
if docker inspect vpnhub-portal-ingress >/dev/null 2>&1; then
    docker exec vpnhub-portal-ingress nginx -t
    docker exec vpnhub-portal-ingress nginx -s reload
else
    rollback() {
        docker rm -f vpnhub-portal-ingress >/dev/null 2>&1 || true
        if [[ -f "$backup/listener.json" ]]; then
            systemctl stop x-ui
            python3 scripts/portal_ingress.py "$backup/listener.json" --restore
        fi
        systemctl start x-ui
    }
    trap 'rollback' ERR
    systemctl stop x-ui
    python3 scripts/portal_ingress.py "$backup/listener.json"
    systemctl start x-ui
    docker run -d --restart unless-stopped --name vpnhub-portal-ingress "${args[@]}" "$image"
    # Validate HTTPS and the unchanged REALITY camouflage SNI through the public listener.
    curl --fail --silent --show-error --retry 8 --retry-all-errors --retry-delay 1 \
        --connect-timeout 3 --max-time 10 --resolve kynnet.space:443:89.125.145.65 \
        https://kynnet.space/web/ -o /dev/null
    curl --silent --show-error --retry 5 --retry-all-errors --retry-delay 1 \
        --connect-timeout 3 --max-time 10 --connect-to www.stackoverflow.com:443:89.125.145.65:443 \
        https://www.stackoverflow.com/ -o /dev/null
    trap - ERR
fi
install -m 644 configs/portal/vpnhub-portal-renew.service /etc/systemd/system/
install -m 644 configs/portal/vpnhub-portal-renew.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now vpnhub-portal-renew.timer
