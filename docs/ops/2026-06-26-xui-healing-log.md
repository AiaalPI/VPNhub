# 2026-06-26 XUI Healing Log

## Incident

VPN health checks were green, but user `76149983` could not connect. Server,
Docker, subscription proxy, TLS, and port `443` were healthy.

## Root Cause

The 3x-ui client `76149983.105.vl` was disabled by the panel after exceeding
the old `10 GB` traffic limit. The bot had extended the key by date, but did
not reset or increase the panel-side traffic limit.

## Production One-Off Fix

Applied on `89.125.145.65`:

- enabled client `76149983.105.vl`;
- reset traffic counters;
- set a defensive `1000 GB` traffic limit;
- verified Xray is active and `443/tcp` is reachable.

## Code Fix

Added panel healing so subscription extensions also restore panel-side access:

- `bot/bot/services/panel_healing_service.py`
- `bot/bot/services/panel_healing_types.py`
- `bot/bot/misc/VPN/Xui/XuiBase.py`
- `bot/bot/misc/VPN/ServerManager.py`
- `bot/bot/services/subscription_mutation_service.py`
- `bot/bot/database/methods/update.py`

New behavior:

- active key extension calls `restore_panel_client_access`;
- 3x-ui client is re-enabled;
- traffic counter is reset;
- traffic limit is set in bytes;
- unsupported panels are skipped without breaking payment/subscription flows;
- structured logs use `event=panel_client_restore` and `event=xui_client_restore`.

## Audit Tool

Added `scripts/audit_xui_active_clients.py`.

Read-only audit:

```bash
docker cp scripts/audit_xui_active_clients.py vpn_hub_bot:/app/audit_xui_active_clients.py
docker exec vpn_hub_bot python /app/audit_xui_active_clients.py
```

Repair mode:

```bash
docker cp scripts/audit_xui_active_clients.py vpn_hub_bot:/app/audit_xui_active_clients.py
docker exec vpn_hub_bot python /app/audit_xui_active_clients.py --apply
```

## Archive Cleanup

Moved stale local artifacts:

- `54` old `bot/bot/img/*_before_ysyakh_*` images to
  `docs/archive/2026-06-ysyakh-assets/`;
- `logs/all.log`, `logs/errors.log`, and Playwright console log to
  `docs/archive/2026-06-local-logs/`.

Final bot images and the `broadcast_10days_ysyakh.png` banner were left in
their active locations.

## Verification

Local:

```bash
pytest tests/test_trial_payments.py -q
python3 -m py_compile scripts/audit_xui_active_clients.py
```

Production spot-check after one-off fix:

- active VLESS keys: `3`;
- all active 3x-ui clients enabled;
- no exhausted active clients;
- generated subscriptions contain `89.125.145.65:443`;
- generated subscriptions contain `security=reality`;
- generated subscriptions do not contain `host.docker.internal`.
