# VPN traffic check, 2026-10-29

All eight currently active profiles passed an HTTPS request through both the
primary and fallback VPN transports: **16/16 HTTP 204 responses, curl exit 0**.
The two profiles whose runtime registration was previously uncertain also passed.
Website profile credentials matched their account database records.

The test ran from the VPN server through its public listener. It confirms
credential acceptance and HTTPS forwarding, but does not establish reachability
from individual Russian ISPs, UDP support, throughput, or long-session stability.
The application health check remained healthy, including database and messaging.
Temporary test clients were stopped after the check. Production services and
customer profiles were not modified.

The previously observed difference between one profile's database expiry and
panel expiry remains unresolved; successful traffic does not resolve that policy
difference. Detailed evidence and identifiers are retained privately by the owner.

Website–Telegram linking remains prepared in PR #25 and is not deployed.
Rollout requires a fresh backup, owner approval, and the documented production
deployment workflow. The audit result alone does not authorize deployment.
