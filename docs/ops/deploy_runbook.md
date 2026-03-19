# Deploy Runbook

## Prerequisites
- Clean git tree
- PR merged to `main`
- GitHub Actions deploy workflow configured
- Server path `/opt/vpnhub/deploy.sh` present and executable

## Canonical Production Path

- Production deploy is triggered by push/merge to `main` via GitHub Actions.
- GitHub Actions connects to the server and runs `/opt/vpnhub/deploy.sh`.
- In this repository, the canonical server entrypoint is the root [deploy.sh](/Users/black/Projects/vpnhub/deploy.sh), which delegates to [server/deploy.sh](/Users/black/Projects/vpnhub/server/deploy.sh).

## Manual Helper

`scripts/orchestrate_v3.sh` remains available as a manual gated helper for investigations and controlled ops work, but it is not the canonical production deployment path.

## Gates
- Preflight must pass (no tracked secrets)
- QA must pass
- Smoke must pass (`Up`, `healthy`, `restart_count=0`, `/health` returns readiness JSON with `status=ok`, no conflict/fatal)
- Triage must report no P0/P1

## Health Contract
- `GET /healthz` — liveness only; process is up.
- `GET /health` — readiness; returns `200` only when DB and NATS are reachable.

## Artifacts
- `.artifacts/triage.md`
- `.artifacts/report.md`
- `docs/ops/taskpacks/<timestamp>-<branch>/`
