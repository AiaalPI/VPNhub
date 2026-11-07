# Subscription recovery through MOW2 — prepared 7 November 2026

## Current verified production

PR #34 is deployed: commit `ce7084388a69cbcdda1bad44641bc1c1d4bcf158`.
MOW2 `89.125.136.14` runs enabled/active `vpnhub-bridge`, TCP 443/2087 to
HEL1 `[2605:e440:7::1:1a8]`. Actions bridge run 42260394424, application run
42260388296 and CI 42260388252 succeeded. Owner confirmed websites/video on
the phone through permanent XHTTP 2087. Temporary old test ports were stopped.
HEL1 remains `194.58.59.48`, application `/opt/vpnhub`, SSH `vpnhub-prod`.

## Prepared change; not active until approved deployment

- `XUI_PUBLIC_ADDRESSES` maps database **server IDs**, not inbound IDs, to
  export-only hosts. It defaults to empty; panel API addresses stay unchanged.
  Activation sets only `{"1":"89.125.136.14"}`. VLESS UUID, port, REALITY
  parameters, expiry and quotas are not changed by the address override.
- Origin subscriptions retain their existing TLS certificate and private key.
  Docker publishes 8443 on IPv6 too. MOW2 passes raw TCP 8443 to that IPv6
  listener; SNI `sub.kynnet.space` on public 443 takes the same route.
  Existing 8443 URLs and signatures are retained; no signing-key rotation.
- MOW2 TCP 80 forwards to origin IPv6 80. Origin serves HTTP-01 from the existing
  portal webroot for `sub.kynnet.space`. A dedicated timer renews this certificate
  using explicit webroot mode, overriding its historical standalone method.
  Both certbot services share a lock and have a 600-second timeout.
- Subscription nginx access logs contain status, bytes and duration only;
  request URI logs are suppressed. No Cloudflare is introduced.
- HAProxy reload is graceful. Its backend preflight now requires 80/8443 too;
  deploy the origin before the updated bridge. Quotas remain shared on HEL1.

## Validation before approval

35 tests passed; one PostgreSQL integration test skipped without its dedicated
database. Coverage includes API/export separation, both VLESS transports,
accounting headers, formats, monthly policy behavior and identity preservation.
Bot Docker build and ru/en msgfmt passed. Candidate nginx configurations passed
`nginx -t` with the existing origin certificate volume; Compose including the
actual production override retains both IPv4 and IPv6 8443 bindings. Shell,
HAProxy and systemd syntax are checked separately.

Isolated alternate-port tests from Mac `en0`, without disabling its other VPN:

- SNI multiplexed HTTPS health: 200; legacy-port HTTPS health: 200, verified TLS.
- Invalid subscription token: 403, rather than exposed configuration.
- Real existing owner's REALITY and XHTTP: HTTPS 204 each.
- HTTP-01 test file traversed IPv4 MOW2 -> IPv6 origin successfully.

Private owner probe files were temporarily stored with the owner's explicit
permission and removed. No private server TLS/REALITY key was exported.
Temporary containers, services, test files and source-restricted UFW rules must
be removed after preflight. Live DNS, exported profiles and production listeners
were not changed during these tests. Actual ACME staging renewal and valid
personal subscription retrieval are final post-deployment checks, not claimed
as completed by the synthetic HTTP-01/invalid-token checks.

## Approved cutover sequence

1. Obtain explicit production/DNS approval. Main merge triggers the standard
   origin deploy, including IPv6 listeners and renewal units. Wait for health.
2. Dispatch `Deploy VPN bridge` and approve its protected environment. Confirm
   HTTPS through MOW2 on 443/8443 using `--resolve`, before changing DNS.
3. Dispatch `Activate MOW2 VPN exports`, mode `enable`, and approve its protected
   environment. The canonical `/opt/vpnhub/deploy.sh subscriptions-origin`
   creates a private server-side backup of `bot/.env`, changes only the export
   mapping and invokes the standard app deploy (with its PostgreSQL backup).
   Concurrent origin deploy workflows share a serialization group.
4. Verify a valid existing owner's subscription through the bridge: all three
   formats, metadata and unchanged UUID/expiry/quota; verify real VPN access.
5. Change only Namecheap A record **sub** to `89.125.136.14`; retain @/panel.
   Google Public DNS preflight: sub A `194.58.59.48`, no AAAA, observed TTL 1799s.
   Recheck actual records before editing. Use a short TTL going forward; old
   cached answers can remain for roughly 30 minutes. No AAAA addition is planned.
6. Verify authoritative/public DNS and direct `en0` subscription retrieval with
   ordinary hostname resolution. Check old Happ subscriptions on the phone.
7. Run certbot renewal `--dry-run --cert-name sub.kynnet.space --webroot` through
   the actual public HTTP-01 path; check the new timer and healthy workloads.

## Recovery limits

Client IDs and entitlement rows have no migration in this change. Keep the
existing direct HEL1 endpoints and the working permanent phone profile.
Restoring old exported addresses is supported by the protected activation
workflow with mode `disable`, followed by its normal deployment. It requires
owner rollback approval; restoring DNS is a separate explicit action. On failed
activation the env file is restored, but containers may already have changed:
inspect them before retrying. Do not claim this is an atomic cross-host rollback.
