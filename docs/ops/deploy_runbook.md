# Deploy Runbook

## Prerequisites
- Clean git tree
- Branch pushed to origin
- SSH access to target host

## Standard command

```bash
./scripts/orchestrate_v3.sh --host r1105660 --branch <branch>
```

## Gates
- Preflight must pass (no tracked secrets)
- QA must pass
- Smoke must pass (`Up`, `healthy`, `restart_count=0`, `/health` contains `ok`, no conflict/fatal)
- Triage must report no P0/P1

## Artifacts
- `.artifacts/triage.md`
- `.artifacts/report.md`
- `docs/ops/taskpacks/<timestamp>-<branch>/`
