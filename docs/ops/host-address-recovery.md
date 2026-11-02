# Restore ingress after a VPS address change

The canonical deployment remains GitHub Actions → `/opt/vpnhub/deploy.sh`.
The application database, XUI database, TLS certificates and deployment SSH
access must be restored before invoking that deployment on a replacement host.
Never overwrite a running production database with a recovery archive.

For a new VPS, create root-owned `/etc/vpnhub/portal-ingress.env` using
`configs/portal/portal-ingress.env.example`. Set `PORTAL_PUBLIC_IPV4` to the
new address assigned to that VPS. Set `PORTAL_PUBLIC_IPV6` to its assigned
IPv6 address, or leave it empty if IPv6 is not configured.

With this file present, canonical deploy renders
`/var/lib/vpnhub-portal/ingress/nginx-shared.conf` and mounts its directory
into the ingress container. The tracked configuration remains clean.
Address syntax is validated before the runtime file is replaced. Wildcard,
loopback, multicast and link-local listeners are rejected to preserve the
separate public ingress and loopback Xray listeners.

Without the per-host file, the existing static deployment configuration is
used. A running ingress with a different configuration mount is rejected;
switching mounts requires an approved maintenance operation. A replacement
VPS has no old ingress container, so its first canonical deployment uses the
new runtime directory directly.

HTTPS bootstrap probes use the selected IPv4 explicitly, retaining normal
hostname and certificate validation. DNS can therefore be updated separately
without accidentally validating the old VPS.

Before deleting the source VPS, verify an encrypted off-site backup and a
restore test, DNS access, GitHub Actions access and the recovery SSH identity.
Preserve VPN client UUIDs, REALITY keys, expiry times, traffic counters and
quotas. Adapt host-specific IP/IPv6/network settings rather than restoring
old network configuration blindly. Update database panel addresses and exported
VPN addresses without extending subscriptions or creating replacement identities.

After recovery, verify readiness, locale compilation and user/admin menus,
public HTTPS and personal subscription delivery, then real HTTPS traffic
through both VPN transports from an external network without another VPN.
Existing profiles containing a literal old IP require subscription refresh
or reimport; preserving UUIDs alone cannot change an already imported address.
