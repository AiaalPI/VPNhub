# 2026-07-10 XUI Certificate and Client Recovery

Last verified: 2026-07-11 10:39 UTC

This document records the production incident, emergency changes, current
state, recovery artifacts, and the actual automation coverage. It intentionally
contains no passwords, panel access path, Telegram bot token, subscription
token, private key, or client UUID.

## Production Topology

- VPS: `89.125.145.65`, SSH alias `vpnhub-prod`
- Application: `/opt/vpnhub`
- Bot container: `vpn_hub_bot`, local health port `8888`
- XUI service: `x-ui.service`, panel version `3.3.1`
- Xray: `26.6.1`, public VLESS/REALITY port `443`
- Panel HTTPS port: `2053`
- XUI subscription HTTPS port: `2096`
- Public subscription proxy: `8443`
- XUI SQLite database: `/etc/x-ui/x-ui.db`
- XUI certificate: `/root/cert/ip/fullchain.pem`
- XUI private key: `/root/cert/ip/privkey.pem`
- ACME home: `/root/.acme.sh`

The hidden XUI panel path and credentials remain in the production database and
environment. Do not copy them into this repository or incident logs.

## Impact

The bot could not authenticate to XUI, so server checks failed and server `1`
was automatically hidden with `auto_work=false`. Existing Xray traffic on port
`443` was still listening, but key delivery, panel inspection, and subscription
generation were affected.

During the emergency creation of key `151`, the new 3x-ui client API replaced
the legacy inbound client list with the two clients known to the new global
client tables. Forty-six active managed clients temporarily disappeared from
the panel view. They were recovered from an intact SQLite base image and all
active clients were verified afterward.

## Root Causes

### 1. Expired panel certificate

The certificate used by XUI expired at:

```text
notAfter=Jul 10 02:52:44 2026 GMT
```

The bot then logged errors matching:

```text
SSLCertVerificationError: certificate has expired
```

### 2. pyxui_async incompatibility with 3x-ui 3.3.1

The installed `pyxui_async==2.0.9` expected older panel behavior:

- `/login/` instead of `/login`;
- no CSRF token request;
- no `X-CSRF-Token` or `X-Requested-With` headers;
- a safe-cookie policy that rejects cookies from an IP host;
- the old `/panel/api/inbounds/addClient` client creation endpoint.

3x-ui `3.3.1` returns its CSRF token in the JSON field `obj` and moved client
creation to a global client API. The initial symptoms were HTTP `403`, followed
by HTTP `404` when the old create-client endpoint was called.

### 3. Mixed legacy and global client storage

The XUI SQLite database contained the working VPN clients in
`inbounds.settings.clients`, while only one seed client had been migrated to the
new `clients` and `client_inbounds` tables. Calling the 3x-ui 3.3.1 global client
create API made the global tables authoritative and reduced the inbound list to
two clients. The API must not be used again until the legacy clients are fully
migrated and validated.

## Emergency Changes

### Certificate renewal

ACME was installed and a Let's Encrypt short-lived IP certificate was issued:

```bash
/root/.acme.sh/acme.sh --set-default-ca --server letsencrypt --force
/root/.acme.sh/acme.sh --issue \
  -d 89.125.145.65 \
  --standalone \
  --server letsencrypt \
  --certificate-profile shortlived \
  --days 6 \
  --httpport 80 \
  --force
/root/.acme.sh/acme.sh --installcert \
  -d 89.125.145.65 \
  --key-file /root/cert/ip/privkey.pem \
  --fullchain-file /root/cert/ip/fullchain.pem \
  --reloadcmd 'systemctl restart x-ui'
chmod 600 /root/cert/ip/privkey.pem
chmod 644 /root/cert/ip/fullchain.pem
```

Current certificate validity:

```text
notBefore=Jul 10 03:23:24 2026 GMT
notAfter=Jul 16 19:23:23 2026 GMT
```

ACME reports the next renewal at `2026-07-13T11:59:50Z`. Root cron runs the
ACME renewal check daily at `11:51` UTC.

### Temporary pyxui_async compatibility patch

The running `vpn_hub_bot` container was patched to support login, CSRF, and IP
cookies. Original package files were backed up with the suffix
`.bak_20260710_csrf`.

The durable repository-side implementation is:

- `bot/bot/misc/VPN/Xui/CompatXUI.py`
- `bot/bot/misc/VPN/Xui/XuiBase.py`

At the time of this incident, these repository changes were local and had not
been merged or deployed through GitHub Actions. Recreating the container can
therefore remove the emergency site-package patch.

The compatibility class fixes authentication only. It does not yet safely
migrate or create clients with the 3x-ui 3.3.1 global client model.

### New key for user 76149983

- No active or expired key existed in the application database.
- Key `151` was created on server `1` for 30 days.
- Expiry: `2026-08-09 05:06` in the configured bot timezone.
- The key and clean subscription link were delivered through the Telegram bot.
- Production logs confirmed HTTP `200` for the new subscription.

### Client-list recovery

Before any repair, all current SQLite files were backed up. The intact base
database contained `48` clients and the live post-incident view contained `2`.
Clients were merged by email into `inbounds.settings.clients`, preserving the
new client `76149983.151.vl` and every previous UUID.

Recovery backup:

```text
/root/xui-recovery-backups/20260710_051533/
  source-base.db
  x-ui.db
  x-ui.db-shm
  x-ui.db-wal
```

Recovery procedure used:

1. Stop `x-ui`.
2. Copy the database, WAL, and SHM files to a timestamped root-only directory.
3. Read the intact clients from `source-base.db`.
4. Read the new client from the live database.
5. Merge by client email; preserve live entries on collisions.
6. Update only inbound `1` client settings in one SQLite transaction.
7. Run `PRAGMA integrity_check` and require `ok`.
8. Start `x-ui` and audit every active database key.

Never copy only `x-ui.db` and assume it is current while WAL mode is active.
Always preserve `x-ui.db`, `x-ui.db-wal`, and `x-ui.db-shm` together, or use a
SQLite online backup after stopping writes.

### 2026-07-11 global-client migration

User `809932233`, key `106`, reported that VPN traffic did not work. The
application database and XUI panel audit were green, but an actual tunnel from
the VPN host was reset. The decisive check was the generated Xray runtime file:

```text
panel inbound clients: 49
global clients: 2
Xray runtime clients on port 443: 2
```

The panel audit had only proved that clients existed in
`inbounds.settings.clients`; it had not proved that Xray loaded them. Xray
3x-ui 3.3.1 generated its runtime configuration from the new global client
tables, so only `admin-seed` and key `151` were active in the core.

With explicit production approval, all `49` inbound clients were migrated in
one SQLite transaction into `clients` and `client_inbounds`. The migration
preserved every email, UUID, `subId`, flow, traffic limit, expiry, enabled flag,
Telegram ID, comment, and timestamps. It did not generate replacement UUIDs.

Consistent pre-migration backup:

```text
/root/xui-global-client-migration-backups/20260711_103819/
```

Postconditions:

```text
global clients: 49
inbound attachments: 49
Xray runtime clients on port 443: 49
SQLite integrity_check: ok
key 106 UUID matches legacy, global, runtime, and exported profile
```

The same-host REALITY canary reset for both key `106` and the known-used key
`151`, so it is not a valid independent end-to-end test for this topology. A
copy of a live user credential to another machine was intentionally rejected.
Future synthetic monitoring must use a dedicated disposable canary identity,
never a real user's key.

### 2026-07-11 traffic policy

With explicit production approval, traffic counters were reset for all `48`
managed clients matching `<telegram_id>.<key_id>.vl`. Each managed client now
has a `100 GB` traffic limit. The service client `admin-seed` remains unlimited.

Monthly reset is configured at the 3x-ui inbound level:

```text
inbound 1 traffic_reset=monthly
```

The per-client `reset=0` field is not the monthly scheduler in 3x-ui 3.3.1;
periodic reset is controlled by the inbound `traffic_reset` value. Current
client counters and global traffic overlays were cleared, and XUI was restarted
so Xray loaded the updated policy.

Production `/opt/vpnhub/bot/.env` now contains `LIMIT_GB=100`, so the next
controlled bot deployment/recreation will use the same limit for newly created
paid clients. The running bot container was not recreated because its emergency
XUI compatibility patch is still container-local.

Traffic-policy backup:

```text
/root/xui-limit-policy-backups/20260711_131718/
```

Postconditions:

```text
managed clients: 48
managed limits: 100 GB
traffic_reset: monthly
runtime clients: 49
SQLite integrity_check: ok
admin-seed limit: unlimited
```

## Verified Final State

- `x-ui.service`: active, `Restart=on-failure`
- Xray: active and accepting TCP connections on `443`
- Bot `/health`: `status=ok`, DB and NATS both true
- Docker services: healthy
- Database server flags: `work=true`, `auto_work=true`
- Active database keys on XUI server `1` at the latest check: `3`
- Active clients missing, disabled, or exhausted: `0`
- XUI panel, global table, attachments, and Xray runtime clients: `49`
- Key `151`: exists, enabled, subscription endpoint returns HTTP `200`
- Key `106`: active through `2026-07-25`, enabled, `23.08/50 GB`, loaded by Xray
- Recovery backup: present and root-only

## Fast Production Checks

```bash
ssh vpnhub-prod "systemctl is-active x-ui"
nc -vz 89.125.145.65 443
ssh vpnhub-prod "curl -sS http://127.0.0.1:8888/health"
ssh vpnhub-prod \
  "docker exec vpn_hub_bot python /app/audit_xui_active_clients.py --server 1"
ssh vpnhub-prod \
  "openssl x509 -in /root/cert/ip/fullchain.pem -noout -issuer -dates"
ssh vpnhub-prod "/root/.acme.sh/acme.sh --list"
```

Useful logs:

```bash
ssh vpnhub-prod "docker logs vpn_hub_bot --since 30m"
ssh vpnhub-prod "journalctl -u x-ui --since '30 minutes ago' --no-pager"
```

Expected audit result:

```text
summary problems=0 restored=0 apply=False
```

## Current Automation Coverage

| Check or repair | Frequency | Current behavior | Limitation |
|---|---:|---|---|
| Bot Docker readiness | 30 seconds | `/health` checks PostgreSQL and NATS | Does not test XUI, port `443`, a subscription, or a VLESS handshake |
| Docker restart policy | On process exit | Restarts main containers with `unless-stopped` | An `unhealthy` status alone does not restart a container |
| XUI systemd restart | On process failure | `Restart=on-failure`, delay 5 seconds | Does not detect a logically broken panel or client list |
| Server control scheduler | 15 minutes | Logs into the panel, counts clients, updates `auto_work`, alerts admin on failure/recovery | Can hide the server, but does not repair TLS, restart XUI, or restore missing clients |
| Existing-client healing | On subscription extension | Enables client, resets traffic, restores limit | Cannot create a missing 3x-ui 3.3.1 client safely |
| Active-client audit | Manual | Compares active DB keys with XUI, detects missing/disabled/exhausted clients | Not scheduled; `--apply` only heals clients that already exist reliably |
| ACME certificate renewal | Daily at 11:51 UTC | Renews short-lived IP certificate and restarts XUI after installation | No separate expiry or renewal-failure alert |
| Prometheus | 15 seconds | Scrapes bot `/metrics`; Grafana is running | No Prometheus alert rules or Alertmanager are configured |
| XUI resync script | Not active | Repository contains `resync_xui_clients.py` and `cron_resync_xui.sh` | No production cron entry; old API and stale topology assumptions make apply mode unsafe |
| Real VPN synthetic test | None | Not implemented | No external probe confirms an actual VLESS/REALITY connection and internet egress |

Production logs confirm that the 15-minute server-control job is running. Root
cron contains ACME renewal, but no XUI integrity/resync job. The `control` user
also has no active resync cron entry.

## Self-Healing Status

The system has partial automatic detection and repair, not full VPN
self-healing. It can restart crashed processes, mark an unreachable server
unavailable, renew the panel certificate, and repair an existing disabled or
traffic-exhausted client during subscription extension.

It cannot currently prove that a user can establish a VLESS/REALITY tunnel,
detect a missing XUI client list immediately, safely recreate missing clients
on 3x-ui 3.3.1, or page an operator through Alertmanager.

## Required Follow-up

1. Add supported create, update, delete, and export methods for the new XUI API,
   with an integration test against 3x-ui 3.3.1.
2. Deploy the durable CSRF/login compatibility code through a branch, PR,
   successful `docker compose build vpn_hub_bot`, and GitHub Actions.
3. Extend the integrity audit to compare DB keys, panel settings, global client
   rows, inbound attachments, and the generated Xray runtime configuration.
4. Add a read-only integrity check every 5 minutes and alert on drift.
5. Add an external synthetic VLESS/REALITY probe using a dedicated canary key.
6. Add certificate-expiry and renewal-failure alerts at 72 and 24 hours.
7. Configure Prometheus alert rules and an Alertmanager route to the admin.
8. Add automated, consistent XUI SQLite backups and a tested restore drill.

The global-client migration is complete, but the bot library still targets the
removed legacy create-client endpoint. Do not rely on automatic XUI client
creation until item 1 is merged, built, deployed, and tested. After any panel
mutation, verify both the active-client audit and the generated Xray runtime
client count before considering the operation complete.

## MTS XHTTP Fallback (2026-07-12)

A second VLESS inbound was added without changing the primary
`VLESS/REALITY/RAW` listener on TCP `443`:

```text
inbound id: 2
tag: inbound-2087-xhttp
transport: VLESS / REALITY / XHTTP
listen port: TCP 2087
traffic reset: monthly
attached clients: 51
```

The VPS already used `bbr` with the `fq` queue discipline, so no kernel sysctl
change was required. TCP keepalive and a 15-second user timeout are configured
on the XHTTP inbound. Port `8443` was unavailable because it belongs to the
public subscription proxy.

The configuration was validated with `xray run -test` before insertion. After
XUI restart, both `443` and `2087` were externally reachable. An end-to-end
synthetic Xray client connected to the public `2087` listener and completed an
HTTPS request through the XHTTP/REALITY tunnel.

Backup created before the successful mutation:

```text
/root/xui-xhttp-backups/20260712_072739/
```

REALITY private material and the randomized XHTTP path remain only in the XUI
database and its root-only backup. They must not be copied into Git.

VPNHub exposes this fallback only when the bot has
`XUI_FALLBACK_INBOUND_IDS=2`. Native subscription output contains the primary
and XHTTP URIs. Generated Clash and sing-box documents intentionally omit the
XHTTP URI when those converters cannot represent it safely.

This is transport redundancy, not host redundancy. Both profiles still use the
same public IP. Xray also warns that REALITY on non-443 ports has a higher
blocking risk, so the long-term design remains a second VPS or second public IP
with XHTTP on TCP `443`.
