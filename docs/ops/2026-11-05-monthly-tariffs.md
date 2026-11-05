# Monthly tariff rollout — 2026-11-05

Owner-approved allowances: trial 50 GiB for the existing configured trial duration;
1 month 300 GiB/month; 3 months 600 GiB/month; 6 months 1000 GiB/month; annual
unlimited. Prices, paid expiry, UUIDs, subscription URLs and transports stay intact.
The owner requested the new allowances for active and new subscribers.

## Accounting

`traffic_policies` stores the activation anchor, next calendar-month boundary,
per-direction baseline counters and an absolute panel ceiling. Months use
Asia/Yakutsk local activation time. January 31 follows February 28/29 then March 31.
Unused traffic never rolls over; downtime across several boundaries grants only
the current month's allowance. The scheduler reconciles every 60 seconds, so an
exhausted profile can take up to one scheduler interval plus panel latency to reopen.

Panel cumulative traffic stays intact. The enforced ceiling is baseline upload +
baseline download + monthly allowance. Happ receives counters minus that baseline
and the monthly allowance. The annual allowance uses genuine `totalGB=0`; monthly
usage still refreshes for display. The baseline and target commit before sending
the panel update; a lost response retries the same target under a database row lock.

Active renewals retain current-month usage and the billing anchor. Selecting a
different term changes its monthly allowance immediately; it does not issue a
second full allowance. Reactivating an expired subscription starts a new cycle.
An external manual panel-counter reset is detected and needs explicit reconciliation;
it is not silently converted into another allowance.

XUI 3.3.1 `reset` auto-renews an expired client and is deliberately disabled for
managed policies. It must not implement the monthly allowance. The installed panel
is retained; no Xray upgrade, Cloudflare or firewall change is needed.

## Existing subscriptions

After the approved code deployment/migration, run the following inside the normal
application environment. Dry-run is default; review every ID and expiry first:

```bash
docker exec -i vpn_hub_bot python - < scripts/migrate_monthly_tariffs.py
# Example overrides only for keys lacking a key-specific receipt:
docker exec -i vpn_hub_bot python - --key-months '{"KEY_ID":1}' < scripts/migrate_monthly_tariffs.py
# Add --apply only after reviewing the complete report.
```

Key-specific paid orders determine the term and earliest known paid activation.
A matched legacy receipt is the next source. Missing historical terms require an
explicit owner mapping; an unknown manual activation anchors at rollout time.
A missing paid term prevents applying the whole migration. Legacy standalone
panel clients without a bot/web entitlement are not changed.

Existing subscribers begin with a fresh monthly allowance at migration: historical
monthly consumption cannot be reconstructed from lifetime counters. The next
refresh uses the original known anchor; no paid expiry is changed. Active trials
get at least 50 GiB without making a recurring free subscription or reopening an
expired trial. Rerunning migration preserves existing policy baselines.

Verify each policy's `applied_at`, global panel UUID/expiry, absolute ceiling,
metadata monthly counters, and both REALITY/XHTTP exports. Scheduler delivery errors
are logged by policy ID and exception class without credentials. A persisted policy
alone is not proof the panel applied its target.

## Preceding release

PR #30 deployed as `4f85aa8` through GitHub Actions run `42045151093` successfully.
External owner subscription exports returned HTTP 200 for VLESS, Clash and sing-box
with identical real accounting. App readiness DB/NATS was OK, bot healthy/restarts 0,
and x-ui active. This release did not change the previous 100 GiB owner allowance.
