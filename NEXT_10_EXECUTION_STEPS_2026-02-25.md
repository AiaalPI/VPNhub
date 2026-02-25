# NEXT 10 EXECUTION STEPS (2026-02-25)

> **Canonical execution driver.** Roadmap context: `TECHNICAL_ROADMAP_2026.md`. Issue details: `GITHUB_ISSUES_BACKLOG.md`.

0. **[P0 BLOCKER] Secrets rotation — complete before any other step.**
   Ref: `AUDIT_REPORT_2026-02-24.md` §РИСК 1 · `GITHUB_ISSUES_BACKLOG.md` Issue #101
   Files: `bot/.env`, `.gitignore`, `bot/.env.example`
   Commands:
   ```bash
   git ls-files | grep "^bot/\\.env$"   # must return empty after fix
   git rm --cached bot/.env
   echo "bot/.env" >> .gitignore
   cp bot/.env bot/.env.example         # then strip all real values
   ```
   Validation: `git ls-files | grep "^bot/\\.env$"` returns empty. Rotate ALL credentials (TG_TOKEN, POSTGRES_PASSWORD, all payment keys) via provider dashboards and update GitHub Actions Secrets before proceeding.

1. Create a sprint branch.
   Files: None
   Commands:
   ```bash
   git checkout -b sprint/2026-02-25-execution
   git status -sb
   ```
   Validation: `git status -sb` shows branch `sprint/2026-02-25-execution`.

2. Add `/health` endpoint with DB + NATS checks.
   Files: `bot/bot/webhooks/base.py`
   Commands:
   ```bash
   rg -n "FastAPI|@app\.get|lifespan" bot/bot/webhooks/base.py
   ```
   Validation: New `/health` route returns JSON with `status=ok` and `details.db=true`, `details.nats=true` (per logs or local curl).

3. Wire container healthcheck to `/health`.
   Files: `docker-compose.yml`
   Commands:
   ```bash
   rg -n "healthcheck|8888" docker-compose.yml
   ```
   Validation: `docker compose ps` shows `vpn_hub_bot` as `healthy` after startup.

4. Add FastAPI request logging middleware.
   Files: `bot/bot/webhooks/base.py`
   Commands:
   ```bash
   rg -n "middleware\(\"http\"\)" bot/bot/webhooks/base.py
   ```
   Validation: After any HTTP request, logs include `event=http_request method=... path=... status=... duration_ms=...`.

5. Add Prometheus client dependency.
   Files: `bot/requirements.txt`
   Commands:
   ```bash
   rg -n "prometheus" bot/requirements.txt
   ```
   Validation: `prometheus_client` appears in `bot/requirements.txt` and `docker compose build vpn_hub_bot` completes.

6. Expose `/metrics` endpoint with basic counters.
   Files: `bot/bot/webhooks/base.py`
   Commands:
   ```bash
   rg -n "metrics|prometheus" bot/bot/webhooks/base.py
   ```
   Validation: `curl -s http://localhost:8888/metrics | head -n 5` returns Prometheus text format.

7. Add Prometheus + Grafana services and config.
   Files: `docker-compose.yml`, `configs/prometheus.yml`
   Commands:
   ```bash
   rg -n "prometheus|grafana" docker-compose.yml
   ```
   Validation: `docker compose up -d prometheus grafana` succeeds and Prometheus UI shows target `vpn_hub_bot` as `UP`.

8. Add China smoke test script.
   Files: `scripts/china_smoke_test.sh`
   Commands:
   ```bash
   rg -n "china_smoke_test" scripts/china_smoke_test.sh
   ```
   Validation: `CN_SOCKS5_PROXY=socks5h://user:pass@host:1080 scripts/china_smoke_test.sh` prints pass/fail and latency.

9. Implement UX onboarding simplification.
   Files: `bot/bot/handlers/user/main.py`, `bot/bot/handlers/user/keys_user.py`, `bot/bot/states/user.py`
   Commands:
   ```bash
   rg -n "location_selection|store_selection|/start" bot/bot/handlers/user/main.py bot/bot/handlers/user/keys_user.py bot/bot/states/user.py
   ```
   Validation: `/start` for a new user goes directly to key delivery without store or location selection.

10. Build the bot image to verify dependencies.
   Files: None
   Commands:
   ```bash
   docker compose build vpn_hub_bot
   ```
   Validation: Build exits with code 0 and no missing dependency errors.

