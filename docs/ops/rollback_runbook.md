# Rollback Runbook

Use when smoke/triage gates fail after deployment.

## Manual rollback

```bash
git log --oneline -n 20
git checkout <previous_commit>
docker compose up -d --build vpn_hub_bot
```

## Post-rollback checks
- `docker compose ps`
- `curl -fsS http://127.0.0.1:8888/health`
- `docker compose logs --tail=300 vpn_hub_bot`

Warning: do not delete DB volumes.
