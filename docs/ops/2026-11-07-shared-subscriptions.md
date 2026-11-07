# Shared website / Telegram subscription

Prepared on 2026-11-07. Production activation requires owner approval of the
reviewed PR, followed by the canonical GitHub Actions deploy. No customer
entitlement has been changed while preparing this release.

## Identity and entitlement

An email login does not identify a Telegram user. A one-time link must be
confirmed in both authenticated channels. Referral IDs, matching display names
and email guesses never establish ownership. Existing confirmed links are
eligible for the same merge during the reconciliation job.

The owner approved these rules:

- Add all remaining paid seconds at the time of the merge. Trial seconds do not
  contribute. Expired records contribute no time.
- Preserve the sum of remaining finite allowances for the first common cycle.
  Any active unlimited paid plan takes priority. At subsequent calendar-month
  boundaries use the largest original active monthly quota.
- Preserve existing UUIDs as aliases, with one aggregate traffic budget and one
  expiry. A trial UUID may remain an alias but adds neither days nor allowance.
- Preserve original purchase records. Member records retain the original
  expiry, quota and baselines for auditing. Repeating the merge adds no time.

The first common monthly boundary is one calendar month after merging, in
Asia/Yakutsk. Month-end dates are clamped, using the existing monthly billing
helper. A subsequent purchase sets the next cycle's plan; an active renewal does
not erase saved allowance or reset usage. An upgrade increases the current
allowance by the quota difference. An expired paid reactivation starts a new
cycle. Unknown *active paid* historical quotas or unsupported panels stop that
account's merge for review rather than inventing an unlimited plan.

## Delivery and accounting

Website and YooMoney bot receipts lock the same account row before updating the
common entitlement. Receipt/order uniqueness remains in place. Both legacy
entitlement adapters receive the same expiry inside the payment transaction.
Panel writes use current absolute values and can be retried after a lost
response. Source UUIDs are pinned when counters are captured; unexpected
replacement/reset is an error, never an automatic new allowance.

The website polls the visible account every two seconds. The latest private
Telegram account message is edited after website fulfillment; a 15-second job
retries reconciliation and view refresh. It sends no new unsolicited messages.
Opening either cabinet reads the committed entitlement directly.

Shared quota enforcement is polling-based, nominally every 15 seconds plus API
latency. Aggregate global counters count each UUID once across REALITY/XHTTP.
Both aliases are disabled when the budget is exhausted; each panel ceiling is
also restricted by the shared remaining budget. This is not an atomic byte
limiter across different UUIDs: concurrent traffic can overrun during a polling
interval, and a control-plane outage delays aggregate enforcement. Existing
per-alias ceilings bound traffic during that outage. Use data-plane shared
accounting if strict instantaneous enforcement becomes a requirement.

Website profiles now export the configured public bridge address, leaving panel
management addresses unchanged. `/subscriptions/web/{sub_id}` provides a stable,
revocable bearer URL in VLESS, Clash and sing-box formats, without browser
cookies. Renewals keep this URL. The URL and raw VPN keys must never be logged.
Existing signed Telegram subscription URLs keep their existing 30-day token
validity; the cabinet supplies the new persistent URL for future imports.
Installed VPN UUIDs continue working independently of subscription URL age.

No DNS provider, Cloudflare, transport endpoint or server location is changed by
this release.

## Release procedure

1. Before approving deployment, create and verify fresh PostgreSQL and XUI
   backups on the origin. Preserve the previous verified recovery set. Do not
   transfer customer databases to another machine without authorization.
2. Review linked active paid keys for unknown quotas and web records without
   purchase/policy/trial evidence. Read-only production preflight on 2026-11-07:
   one confirmed link, zero linked active paid TG keys with unknown quota, zero
   linked active web subscriptions lacking payment/policy/trial evidence.
3. Deploy through GitHub Actions and `/opt/vpnhub/deploy.sh` only. Migration
   `70a8b9c0d1e2` adds shared entitlement/member/message tables. The scheduler then
   merges eligible confirmed links; linking and subsequent receipts use the same
   idempotent service.
4. Verify both cabinets, one controlled renewal in each channel, duplicate
   receipt handling, common expiry/headers, both original UUIDs and shared usage.
   Check `shared_subscription_sync_failed` and `account_view_refresh_failed`
   events. Never publish signed URLs or client UUIDs in verification output.
5. Do not downgrade by dropping the new tables or restoring only PostgreSQL:
   panel state and mirrored legacy expiries have changed. Use a reviewed forward
   repair, or a coordinated PostgreSQL/XUI recovery with owner approval.

## Validation

The regression suite covers both payment channels, concurrent PostgreSQL
receipts, migration, replay, trial exclusion, preserved UUIDs, summed leftovers,
exhaustion, monthly reset, paid reactivation, unlimited priority, lost panel
responses, counter/UUID replacement, private Telegram view edits and stable
public URLs. PostgreSQL uses a temporary localhost-only container and random
schemas with synthetic identities. The browser regression exercises the actual
account JavaScript without sending email or charging a provider.
