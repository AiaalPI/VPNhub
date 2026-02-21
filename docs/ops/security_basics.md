# Security Basics

- Never print secrets to logs.
- All orchestrator scripts redact sensitive patterns with `mask()`.
- Secret scan uses tracked files only (`git ls-files`) to avoid scanning runtime secrets.
- `bot/.env` must never be tracked.
- Use deploy branch workflow; avoid direct unreviewed main deploys.
- Prefer `git reset --hard origin/<branch>` on server deploy target to avoid drift.
