#!/usr/bin/env bash
# Explicitly approved Actions cutover only; never change the panel API endpoint.
set -euo pipefail
[[ $# -le 1 && $EUID == 0 ]] || exit 2
mode="${1:-enable}"
case "$mode" in enable|disable) ;; *) exit 2 ;; esac
cd /opt/vpnhub
# The bridge and TLS route must be ready before new profiles are issued.
if [[ "$mode" == enable ]]; then
    curl --noproxy '*' --fail --silent --show-error --connect-timeout 5 --max-time 10 \
        --resolve sub.kynnet.space:8443:89.125.136.14 \
        https://sub.kynnet.space:8443/healthz >/dev/null
fi
backup="/root/vpnhub-backups/mow2-export-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$backup"
install -m 600 bot/.env "$backup/bot.env"
python3 - "$mode" <<'PY'
import json, os, re, sys, tempfile
from pathlib import Path
path = Path('bot/.env')
lines = [line for line in path.read_text().splitlines()
         if not re.match(r'^\s*(?:export\s+)?XUI_PUBLIC_ADDRESSES\s*=', line)]
mapping = {'1': '89.125.136.14'} if sys.argv[1] == 'enable' else {}
lines.append('XUI_PUBLIC_ADDRESSES=' + json.dumps(mapping))
with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
    temporary = Path(out.name)
    out.write('\n'.join(lines) + '\n')
try:
    temporary.chmod(0o600)
    os.replace(temporary, path)
finally:
    temporary.unlink(missing_ok=True)
PY
if ! bash server/deploy.sh; then
    install -m 600 "$backup/bot.env" bot/.env
    echo 'Export env restored; inspect running containers before retrying deployment' >&2
    exit 1
fi
echo "Export address mode: $mode; previous env: $backup/bot.env"
