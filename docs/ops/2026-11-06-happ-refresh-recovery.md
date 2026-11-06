# Happ refresh recovery — 2026-11-06

After the monthly tariff rollout, the owner's XUI client was deleted and recreated
by the existing same-server selection path. The new counters were lower than the
saved lifetime baselines. Accounting correctly rejected that discontinuity, but
subscription rendering propagated the exception and returned HTTP 500; cached
Happ profiles then retained the old client identity.

The current owner's ledger was explicitly reconciled to the already-created
client's counters, retaining its 300 GiB cap, next billing boundary and paid expiry.
No live counter or client credential was changed by that repair. Audit receipt:
`/root/vpnhub-backups/owner-ledger-repair-20261105T152351Z.json`.
VLESS/Clash/sing-box exports returned HTTP 200 again. Independent HTTPS probes
through both current profiles returned Google generate_204 HTTP 204 via en0.
This checks the probing Mac's route, not every mobile operator or Happ cache.

The code fix preserves an existing VLESS client when its current server is selected
again, including its UUID, accounting and assignment during a temporary panel error.
Optional accounting reconciliation no longer prevents exporting connection links.
Payment provisioning still requires reconciliation to succeed. When the accounting
transaction rolls back, exports use the primitive requested key ID rather than
accessing an expired ORM instance. Invalid accounting is still omitted, not silently
converted into zero usage/unlimited traffic, and unexpected counter resets are not
automatically forgiven for other subscribers.
