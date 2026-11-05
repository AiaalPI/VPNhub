# Subscription accounting and shared VPN capacity — 2026-11-05

## Subscription metadata change

Telegram subscription exports (plain VLESS, Clash and sing-box) read the global
XUI client accounting record and send exact byte counters in
`subscription-userinfo`: `upload`, `download`, `total`, plus the database expiry.
One UUID is shared by REALITY and XHTTP, so its aggregate traffic is included once.
The panel's actual `totalGB` is authoritative for the enforced allowance, including
legacy 100 GiB profiles and genuinely unlimited (`totalGB=0`) records.

The reader verifies key ownership and never updates expiry, allowance, enabled
state, UUID, or counters. A missing, malformed or unavailable accounting response
omits the optional userinfo header rather than replacing previous accounting with
fabricated zero usage and unlimited allowance. Exported connection payloads remain
available. Accounting requests have a six-second deadline and close their session.
The data refreshes when the VPN application refreshes the subscription; it is not
a live speed meter. Other VPN-panel types retain working payload exports but do
not receive invented XUI accounting values.

## Tariff allowance

Source: `bot/bot/misc/tariffs.py`.

| Access | Allowance |
|---|---:|
| Trial | 10 GiB |
| 1 month | 50 GiB |
| 3 months | 150 GiB |
| 6 months | 300 GiB |
| 12 months | 600 GiB |

These are purchased byte allowances, not a monthly-reset job or speed limits.
Renewals must preserve used traffic. Existing accounts can have a different
legacy or accumulated allowance; displaying metadata must not rewrite it.

## Capacity and BitTorrent: observed state, not a new deployment

Read-only inspection of HEL1 on 2026-11-05 found:

- Provider service specifies a shared 400 Mbit/s port; this is not a dedicated
  400 Mbit/s guarantee for every subscriber or every external route.
- Xray 26.6.1 has sniffing enabled (`metadataOnly=false`) on ports 443 and 2087.
- Routing sends detected `bittorrent` to the `blocked` blackhole outbound.
- `eth0` already uses `fq_codel`; no subscriber speed ceiling is configured.
- Panel accounting includes legacy 100 GiB clients and one enabled unlimited
  record. Do not reduce, reset or delete existing allowances as a metadata fix.

An isolated localhost-only test using the installed production Xray binary passed:
normal TCP reached a test listener; a standard BitTorrent TCP handshake reached it
without the block rule and was blocked with the production rule. The production
VPN process and configuration were not changed. This verifies ordinary BitTorrent
TCP detection, not exhaustive detection of encrypted P2P, DHT, or every client path.

Protocol blocking alone cannot guarantee fair per-subscriber bandwidth. Flow
fairness (`fq_codel`) is also not an authenticated per-UUID speed limiter: clients
can open many flows. A stronger policy needs an explicitly selected subscriber
ceiling or a gateway able to classify authenticated subscribers, plus queue/load
measurements and controlled rollout. Do not install a nominal 100 Mbit/s per-IP
rule and describe it as per-subscription enforcement (CGNAT and changing client
addresses invalidate that equivalence).

The owner asked about the maximum available speed before selecting a subscriber
ceiling. No new ceiling or quota reductions have been approved or applied.

## Release

Apply application changes through a branch/PR, successful Docker build and the
existing GitHub Actions `/opt/vpnhub/deploy.sh` path, with owner deployment approval.
Verify a refreshed subscription includes the panel's actual byte counters and
allowance, while UUIDs, expiry and both connection ports remain unchanged.
