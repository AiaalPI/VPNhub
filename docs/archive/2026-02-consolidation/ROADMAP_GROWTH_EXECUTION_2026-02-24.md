# ARCHIVED — superseded by TECHNICAL_ROADMAP_2026.md + GITHUB_ISSUES_BACKLOG.md
> Date: 2026-02-26
> Reason: consolidation — Part 1 strategy merged into TECHNICAL_ROADMAP_2026.md; Part 2 backlog merged into GITHUB_ISSUES_BACKLOG.md (Epic 9+); Parts 3-4 checklists merged into docs/checklists/CHECKLISTS_BY_DOMAIN.md.

---

# VPNHub — Growth Execution Roadmap

**File:** `ROADMAP_GROWTH_EXECUTION_2026-02-24.md`  
**Date:** 2026-02-24  
**Owner:** Principal SaaS Architect / Head of Engineering  
**Scope:** Growth + UX + Reliability + China readiness + Scaling  
**Inputs (in-repo):** `AUDIT_REPORT_2026-02-24.md`, `TECHNICAL_ROADMAP_2026.md`, `ROADMAP_QUICK_REFERENCE.md`, `AI_AGENTS_ANALYSIS.md`, `AI_AGENTS_QUICK_SUMMARY.md`, `docs/ROADMAP.md`, `docs/runbook.md`

This document is the execution-ready roadmap for systematic growth. It is intentionally specific: which files to change, what to ship, and how to verify.

---

## Part 1 — Strategic Roadmap (Refactor)

### Vision
Build the most reliable “connect in 60 seconds” Telegram-first VPN product for restricted networks (China-first), with a measurable funnel from onboarding to paid renewal and self-healing infra that does not page humans for routine incidents.

### North Star Metric (NSM)
**Paid Active Subscribers (PAS)**  
Reason: PAS is the best proxy for revenue + retention and correlates with infrastructure costs and scaling needs.

### KPI System (what we measure weekly)
**Funnel & UX**
- `MTFC` (Mean Time To First Connection): p50/p95 from `/start` to “key delivered” and “client confirmed working”.
- Trial activation rate: `% new users who activate trial`.
- Trial→Paid conversion: `% trial users who pay within trial+7 days`.
- Payment success rate: `% pay attempts leading to confirmed subscription`.
- Support contact rate: `% WAU who open support or send issue`.

**Reliability & Self-healing**
- Uptime: `% time vpn_hub_bot is healthy` (container health + polling running).
- Restart rate: `restarts/day` per service (bot/postgres/nats).
- Key provisioning success: `% key provision calls succeed on first attempt`.
- Auto-remediation success: `% server incidents resolved without admin action`.

**China readiness**
- “CN success rate”: `% CN cohort that completes first connection` (measured via protocol selection + retries; see instrumentation tasks).
- Protocol fallback success: `% sessions where fallback path succeeds`.

### 30/60/90 Day Goals (concrete)

#### 0–30 Days (Stabilize, Measure, Remove Growth Blockers)
**Goal:** no more blind operations; basic funnel telemetry; onboarding and trial flow do not dead-end; infra won’t silently degrade.

Ship list:
1. **Define and enforce health contract**
   - Add `/health` endpoint to FastAPI app (currently missing; compose healthcheck uses `/docs`).
   - Switch compose healthcheck to `/health`.
   - Verification:
     - `curl -fsS http://127.0.0.1:8888/health` returns JSON `{status:"ok"}`.
     - `docker inspect vpn_hub_bot ... Health=healthy` stays healthy under load.
   - Files:
     - `bot/bot/webhooks/base.py`
     - `docker-compose.yml` (healthcheck endpoint change)

2. **Hard gate: secrets hygiene**
   - Ensure `bot/.env` is not tracked; rotate compromised secrets if previously committed.
   - Verification:
     - `git ls-files | rg -n "^bot/\\.env$"` returns empty.
     - CI preflight fails if secret patterns present (see ops orchestrator scripts if enabled).
   - Files:
     - `.gitignore`
     - `docs/ops/security_basics.md` (if exists) + `docs/runbook.md` update

3. **Funnel instrumentation (no behavior changes)**
   - Ensure conversion middleware logs events for key actions (`/start`, connect click, back to menu, help open, pay open, pre_checkout).
   - Verification:
     - `docker compose logs vpn_hub_bot | rg "event=conv\\."` shows expected events.
   - Files:
     - `bot/bot/middlewares/conversion_events.py`
     - `bot/bot/main.py` (middleware wiring only)
     - `docs/analytics/funnel_events.md`

4. **User journey P0 fixes**
   - Fix missing callback handlers (unhandled callbacks cause “dead buttons”).
   - Add recovery keyboards for FSM entry points and validation errors (Back/Main menu).
   - Verification:
     - QA callback audit script returns exit code 0.
     - Manual checklist: user never gets stuck without “Back/Main menu”.
   - Files:
     - `scripts/qa/check_callbacks.py`
     - `docs/qa/callback_audit.md`
     - `bot/bot/handlers/**` only if strictly needed to wire missing callbacks (do not refactor business logic).

#### 31–60 Days (Conversion + Retention)
**Goal:** improve trial→paid conversion and reduce support load via better onboarding and resilient key provisioning.

Ship list:
1. **Onboarding: first connection playbook**
   - First-run wizard: “choose device → copy key → open client → verify”.
   - A/B copy experiments and CTA reordering; keep RU/EN parity.
   - Verification:
     - MTFC p95 < 90 seconds.
     - Trial activation rate +15% vs baseline.
   - Files:
     - `bot/bot/handlers/user/main.py` (start/menu copy only)
     - `bot/bot/locale/**/bot.po` (microcopy)
     - `docs/conversion/experiments.md` (spec)

2. **Payment reliability**
   - Idempotency per webhook provider (Cryptomus/Wata already present; ensure uniform).
   - Introduce “payment pending” state UX + retry.
   - Verification:
     - Payment success rate > 98%.
     - Duplicate webhook does not double-extend subscription.
   - Files:
     - `bot/bot/handlers/payment_webhook.py`
     - `bot/bot/misc/Payment/**`

3. **Retention: expiry + renewal UX**
   - 7d/3d/24h reminders with actionable “Renew” CTA and device-specific instructions.
   - Verification:
     - Renewal conversion +10% over baseline.
   - Files:
     - `bot/bot/misc/loop.py` (existing expiry logic)
     - `bot/bot/handlers/user/payment_user.py` (renew CTA)
     - `bot/bot/locale/**/bot.po`

#### 61–90 Days (Auto-failover + China readiness + Scaling foundations)
**Goal:** automatic server reassignment, protocol fallback, and scale-ready state storage.

Ship list:
1. **Auto-failover v1 (server health scoring + exclusion + reassignment)**
   - Health inputs: latency, error rate, connected users, disk/CPU if available.
   - On unhealthy: exclude server, reassign new keys, notify impacted users/admin.
   - Verification:
     - Failover completes < 60 seconds for 95% users.
   - Files:
     - `bot/bot/service/server_controll_manager.py`
     - `bot/bot/misc/VPN/ServerManager.py`
     - `bot/bot/database/models/servers.py` (if needed for health fields)

2. **China “protocol fallback ladder”**
   - Default: VLESS/Reality (or best available in stack), fallback to Shadowsocks/Outline.
   - Add UX: “Try alternative protocol” button after failure.
   - Verification:
     - CN cohort connection success +X% (measure and iterate).
   - Files:
     - `bot/bot/misc/VPN/**`
     - `bot/bot/handlers/user/**` (UX only; do not change entitlement logic)

3. **Scale readiness**
   - Replace in-memory FSM storage with Redis (multi-instance-safe).
   - Replace file lock with distributed lock (Redis or NATS KV leader election).
   - Split bot and worker responsibilities (polling vs NATS consumers) if needed.
   - Verification:
     - Two instances can run without Telegram conflict or duplicated jobs.
   - Files:
     - `bot/bot/main.py` (storage + startup)
     - `bot/run.py` (leader election / lock)

### 12-Month Strategy (growth + platform)
**Q2 2026: China expansion + conversion engine**
- Protocol ladder stable, fallback domains/ports, CN monitoring.
- Conversion engine: experiments pipeline (copy/CTA/payment), retention playbook.

**Q3 2026: Platform scale**
- Multi-instance bot + separate workers, shared state (Redis), proper health and SLOs.
- Observability: error tracking + alerting + backup automation + restore drills.

**Q4 2026: Enterprise & partnerships**
- B2B tier, affiliate/referral profitability, operational analytics, API integration points.

---

## Part 2 — Backlog (GitHub Issues Format)

All issues are designed to be created as GitHub issues. Use labels: `epic`, `P0/P1/P2`, `growth`, `ux`, `china`, `reliability`, `observability`, `payments`.

### EPIC: Funnel + Conversion Engine
Описание: собрать измеримый funnel и сделать системную оптимизацию trial→paid с A/B тестами.
Почему важно: рост MRR через конверсию, снижает CAC.
Как влияет на рост: +20–40% revenue при том же трафике.

Issues:

Title: Add funnel event taxonomy + baseline dashboard
Priority: P0
Impact: High
Effort: M
Dependencies: none
Risk level: Low
Description: стандартизировать события и обеспечить сбор базовых метрик на уровне логов и (позже) метрик.
Subtasks:
- [ ] Define event list in `docs/analytics/funnel_events.md`
- [ ] Ensure middleware emits `event=conv.*` for `/start`, connect click, help open, pay open, pre_checkout
- [ ] Add grep-based “how to measure” commands in docs
Acceptance Criteria:
- measurable outcome: at least 5 funnel events appear in logs for real sessions
- how to verify: `docker compose logs vpn_hub_bot | rg "event=conv\\." | head`
Definition of Done:
- code: middleware exists and is wired
- tests: compileall passes
- deploy: docker build passes
- monitoring: docs show how to aggregate counts
- documentation: updated analytics docs

Title: Improve /start UX: 3-day trial CTA + “Connect VPN” as primary
Priority: P0
Impact: High
Effort: S
Dependencies: localization strings
Risk level: Low
Description: сократить приветствие до 2–3 строк, добавить явную CTA “3 дня”, вывести “Подключить VPN” первым.
Subtasks:
- [ ] Update RU/EN copy in `bot/bot/locale/**/bot.po`
- [ ] Ensure main menu layout has primary connect CTA
- [ ] Ensure existing-user start highlights connect CTA
Acceptance Criteria:
- measurable outcome: MTFC decreases vs baseline
- how to verify: manual run + conv logs show connect click rates increasing
Definition of Done:
- code: handlers only change copy/markup
- tests: `pytest -q` passes
- deploy: docker build passes
- monitoring: conv events captured
- documentation: experiment entry added

Title: Payment UX: Pending state + retry copy
Priority: P1
Impact: High
Effort: M
Dependencies: payment webhook idempotency
Risk level: Medium
Description: при открытии оплаты показать понятный “ожидаем подтверждение” и путь восстановления; не менять платежную логику.
Subtasks:
- [ ] Add consistent “pending” microcopy and retry CTA
- [ ] Ensure duplicate webhook is idempotent across providers
Acceptance Criteria:
- measurable outcome: payment support tickets decrease
- how to verify: log rate of `payment.*error` and support opens
Definition of Done: code + tests + deploy + docs

### EPIC: Self-healing + SLO-Driven Reliability
Описание: уменьшить restart loops, сделать диагностируемость, сократить MTTR.
Почему важно: надежность прямо влияет на конверсию и retention.
Как влияет на рост: меньше churn и меньше затрат на поддержку.

Issues:

Title: Add FastAPI /health endpoint and use it in healthcheck
Priority: P0
Impact: High
Effort: S
Dependencies: none
Risk level: Low
Description: `/health` должен быть быстрым, без секретов, возвращать 200/503.
Subtasks:
- [ ] Implement `GET /health` in `bot/bot/webhooks/base.py`
- [ ] Update `docker-compose.yml` healthcheck to `http://127.0.0.1:8888/health`
Acceptance Criteria:
- measurable outcome: `/health` returns non-empty JSON and 200 when DB ok
- how to verify: `curl -fsS http://127.0.0.1:8888/health`
Definition of Done: code + deploy + docs

Title: Add resource limits + stop_grace_period audit
Priority: P0
Impact: High
Effort: S
Dependencies: none
Risk level: Medium
Description: ограничить CPU/mem, предотвратить OOM cascading failures.
Subtasks:
- [ ] Define limits for bot/postgres/nats in compose
- [ ] Validate no OOM/restart during load
Acceptance Criteria: restart rate < 1/day under expected load
Definition of Done: config + runbook update

Title: Distributed single-leader protection (replace /tmp lock)
Priority: P1
Impact: High
Effort: M
Dependencies: Redis or NATS KV
Risk level: Medium
Description: текущий `fcntl` lock в `bot/run.py` не работает в multi-instance.
Subtasks:
- [ ] Implement leader election via Redis (SETNX) or NATS KV
- [ ] Ensure only one polling instance runs
Acceptance Criteria: 2 replicas do not conflict
Definition of Done: code + docs + smoke

### EPIC: Auto-failover (Server Switching)
Описание: автоматическая смена сервера при деградации без ручных действий.
Почему важно: качество соединения и доступность ключей определяют retention.
Как влияет на рост: меньше churn, выше NPS, ниже нагрузка на саппорт.

Issues:

Title: Server health model + scoring
Priority: P1
Impact: High
Effort: M
Dependencies: DB schema for health fields
Risk level: Medium
Description: добавить health score per server, хранить историю ошибок/латентности.
Subtasks:
- [ ] Add health fields to `servers` model (score, last_check_at, last_error)
- [ ] Add periodic checker job in scheduler (already exists scheduler usage)
- [ ] Log `event=server.health` structured
Acceptance Criteria: unhealthy servers detected within 60s
Definition of Done: code + migration + docs

Title: Auto reassignment on unhealthy server
Priority: P1
Impact: High
Effort: L
Dependencies: health score, key provisioning
Risk level: High
Description: при деградации сервера — исключить его из выбора и переместить активных пользователей на альтернативу с инструкциями.
Subtasks:
- [ ] Define reassignment rules and safety checks (no data loss)
- [ ] Implement reassignment worker (NATS job) to avoid blocking polling
- [ ] Add user-facing “your server changed” messaging
Acceptance Criteria: 95% impacted users can reconnect within 5 minutes
Definition of Done: code + tests + runbook

### EPIC: China Readiness
Описание: соединение работает под DPI и блокировками (CN first).
Почему важно: рынок и пользовательская боль; качество CN определяет viral spread.
Как влияет на рост: расширение TAM, повышение conversion у CN cohort.

Issues:

Title: Protocol fallback ladder (CN)
Priority: P1
Impact: High
Effort: L
Dependencies: VPN protocol modules in `bot/bot/misc/VPN/**`
Risk level: High
Description: реализовать и измерять fallback цепочку протоколов и портов; добавить UX восстановления.
Subtasks:
- [ ] Define ladder (VLESS/Reality → Shadowsocks/obfs → Outline)
- [ ] Add “Try another protocol” UX after failure
- [ ] Instrument success/failure per protocol
Acceptance Criteria: CN connect success improves measurably vs baseline
Definition of Done: code + docs + experiment plan

Title: Domain/port rotation strategy spec
Priority: P2
Impact: Medium
Effort: M
Dependencies: infra/DNS
Risk level: Medium
Description: подготовить домены/порты/серты для ротации и отката.
Subtasks:
- [ ] Create inventory doc and runbook steps
- [ ] Add monitoring and test plan from CN IP
Acceptance Criteria: rotation can be performed in < 30 minutes
Definition of Done: docs + runbook

---

## Part 3 — Checklists (by Domain)

### 1) USER EXPERIENCE CHECKLIST
- Onboarding
  - [ ] `/start` is 2–3 actionable lines, primary CTA “Connect VPN”
  - [ ] New user gets trial info and a key in one flow
  - [ ] Existing user sees main menu with connect CTA first
- First connection
  - [ ] Device-specific instructions (iOS/Android/PC) accessible from key screen
  - [ ] “Verify VPN” action exists and is clear
  - [ ] Failure path has “Try another protocol” and “Support”
- Payment
  - [ ] Clear tariff selection and price formatting
  - [ ] Payment pending + retry guidance
  - [ ] Duplicate webhook does not double-charge/extend
- Renewal
  - [ ] Renewal reminders at 7d/3d/24h with one CTA
  - [ ] Renewal keeps same device instructions available
- Support
  - [ ] Support screen says what to include (issue + screenshot + device + protocol)
  - [ ] Support flow never traps user (Back/Main menu)
- Multi-device
  - [ ] User can fetch key again
  - [ ] Clear limits and device count policy (if any)

### 2) CHINA READINESS CHECKLIST
- Protocols
  - [ ] VLESS/Reality available and documented
  - [ ] Shadowsocks/obfs fallback available
  - [ ] Outline fallback available
- Fallback
  - [ ] Protocol fallback ladder implemented
  - [ ] Port fallback (443/8443/2053/2083 etc) supported
- Domains
  - [ ] Domain rotation inventory documented
  - [ ] TLS cert rotation runbook exists
- Monitoring
  - [ ] CN cohort success tracked via events
  - [ ] Alerts on CN failure spike
- Testing
  - [ ] Monthly test from CN IP (VPS or proxy) documented and executed

### 3) AUTO-FAILOVER CHECKLIST
- Health checks
  - [ ] Health score computed per server
  - [ ] Error rate tracked per protocol/server
- Latency measurement
  - [ ] Latency probe from bot to server
  - [ ] Use rolling window, not single sample
- Node exclusion
  - [ ] Exclude unhealthy server from selection
  - [ ] Auto re-include after recovery with cool-down
- Auto reassignment
  - [ ] Reassign impacted users safely (no data loss)
  - [ ] Inform users with new key + instructions
- Config regeneration
  - [ ] Regenerate client config and verify key validity

### 4) OBSERVABILITY CHECKLIST
- Health endpoint
  - [ ] `/health` exists and checks DB minimally
- Structured logging
  - [ ] `event=*` convention for major actions
  - [ ] Request/Update IDs present where possible
- Error monitoring
  - [ ] Centralized error tracking (Sentry or equivalent) planned
  - [ ] Alert on `event=runtime.fatal` and restart loops
- Alerting
  - [ ] Alerts for Telegram conflict/unauthorized
  - [ ] Alerts for payment webhook failures
- DB backup
  - [ ] Automated backup with retention
  - [ ] Restore drill documented and tested quarterly

### 5) AI AGENTS CHECKLIST
- DevOps agent
  - [ ] Preflight secret scan (tracked files only)
  - [ ] QA gate (compileall, callback audit, tests)
  - [ ] Deploy + smoke + triage gates
- Monitoring agent
  - [ ] Log triage (P0/P1/P2) with dedup signatures
  - [ ] Taskpack generation for incidents
- Growth agent
  - [ ] Experiment templates + KPI tracking rules
  - [ ] Copy pack RU/EN governance
- Abuse detection agent
  - [ ] Rate limiting and anomaly detection plan
  - [ ] Fraud signals for payments/referrals

---

## Part 4 — Sprint Plan (4 sprints)

### Sprint 1 (2 weeks): Measure + Remove P0 blockers
Goals:
- Health contract (`/health`), secrets hygiene, funnel telemetry baseline, eliminate dead buttons.
Tasks:
- P0: `/health` endpoint + healthcheck switch
- P0: secrets removal/rotation plan executed
- P0: callback audit script in CI and fixed missing callbacks
- P0: /start and trial CTA copy improvements (RU/EN)
Measurable outcomes:
- MTFC baseline captured
- `PAS` baseline captured (even if manual)
- bot `Health=healthy` stable, `RestartCount=0`

### Sprint 2: Conversion uplift + payment reliability
Goals:
- Increase trial activation and payment success; reduce support contacts.
Tasks:
- Payment pending UX + retry copy
- Renewal reminders UX improvements
- Instrument pay open + pre_checkout + payment confirmed events
Measurable outcomes:
- Trial→Paid +2–3pp vs baseline
- Payment success > 98%

### Sprint 3: Auto-failover v1 + retention
Goals:
- Detect and remediate unhealthy servers; keep users connected.
Tasks:
- Server health scoring + exclusion
- Auto reassignment worker via NATS
- User comms for server switching
Measurable outcomes:
- Failover success 95% within 5 minutes
- Support load down

### Sprint 4: China ladder + scale readiness
Goals:
- CN readiness improvements and multi-instance readiness.
Tasks:
- Protocol fallback ladder + UX
- Redis FSM storage + distributed lock design/implementation
Measurable outcomes:
- CN success rate measured and improved
- Two instances can run safely (no conflicts, no double jobs)

---

## Part 5 — Next 10 Execution Steps (Today →)

1) Baseline metrics capture
- Commands:
  - `docker compose logs --tail=500 vpn_hub_bot | rg "event=conv\\." | sort | uniq -c`
- Verify: you can count `conv.start`, `conv.connect_click`, `conv.pay_open`.

2) Implement `/health` endpoint
- Files to change:
  - `bot/bot/webhooks/base.py`
- Verify:
  - `curl -fsS http://127.0.0.1:8888/health`

3) Switch healthcheck to `/health`
- Files to change:
  - `docker-compose.yml`
- Verify:
  - `docker compose ps` shows `vpn_hub_bot (healthy)`

4) Secrets hygiene check
- Commands:
  - `git ls-files | rg "^bot/\\.env$" && exit 1 || true`
- Files to change:
  - `.gitignore` (ensure `bot/.env` ignored)

5) Callback coverage audit in CI
- Files to change:
  - `.github/workflows/ci.yml` (run `scripts/qa/check_callbacks.py` if present)
- Verify:
  - CI fails when missing callback is introduced.

6) Fix dead buttons / missing handlers (P0 UX)
- Files to change:
  - `bot/bot/handlers/**` (only add missing callback handlers; no refactor)
- Verify:
  - Manual: no “silent” inline button presses.

7) /start microcopy + 3-day trial CTA (RU/EN parity)
- Files to change:
  - `bot/bot/locale/ru/bot.po`
  - `bot/bot/locale/en/bot.po`
- Verify:
  - Rebuild image and verify texts in bot.

8) Payment “pending + retry” microcopy
- Files to change:
  - `bot/bot/handlers/user/payment_user.py`
  - `bot/bot/locale/**/bot.po`
- Verify:
  - Simulated payment attempt shows recovery guidance.

9) Auto-failover spec as code TODOs
- Files to change:
  - `docs/runbook.md` (add operational spec and acceptance metrics)
  - `docs/architecture.md` (describe worker separation plan)
- Verify:
  - Engineers can implement without guessing.

10) Release checklist for production
- Commands:
  - `pytest -q`
  - `python -m compileall -q bot`
  - `docker compose build vpn_hub_bot`
- Verify:
  - Build passes; no regressions.

---

## Appendix — Current Repo Reality (facts, not assumptions)
- Compose services: `postgres:16.4`, `nats:2.10.x`, sidecar `nats-health`, `nats-migrate`, `vpn_hub_bot`, `pgadmin`.
- Healthcheck currently hits `/docs`; `/health` endpoint is missing (FastAPI app exists at `bot/bot/webhooks/base.py`).
- Trial expiry logic exists in `bot/bot/misc/loop.py` (uses `trial_expires_at`).
- Payments exist (multiple providers) and webhook routes exist (e.g. Wata `POST /payments/wata/webhook`).
- NATS reconnect is configured (`allow_reconnect=True`, `max_reconnect_attempts=-1`) in `bot/bot/misc/nats_connect.py`.
- KR3: 24/7 Chinese support operational

**O4: Establish product analytics baseline**
- KR1: All funnel events tracked (80+ action types)
- KR2: Dashboards built (real-time funnel, retention, LTV)
- KR3: 100% of critical paths instrumented

---

## DETAILED GROWTH ROADMAP BY QUARTER

### Q1: Foundation + Conversion Optimization

#### Month 1: Stabilize (Days 1-30)
**Theme:** Production rock-solid + full observability

**Week 1-2:**
- Deploy P0 fixes (secrets, /health, backups)
- Setup Prometheus + Grafana
- Baseline all metrics

**Week 3-4:**
- Server health monitoring live
- First auto-remediation scripts
- Trial→paid funnel instrumentation

**Success Criteria:**
- Zero unplanned downtime
- Dashboard shows all key metrics real-time
- Team can identify top churn reasons

**Revenue Impact:** +0% (prep phase)

---

#### Month 2: Optimize (Days 31-60)
**Theme:** 20% improvement in conversion

**Implement UX Agent findings:**
- Remove 2 clicks from trial sign-up (target: < 60 seconds)
- Add payment method 2 + 3
- Add countdown timer for trial expiry
- A/B test: urgent vs patient messaging

**Server Layer:**
- Auto-failover implementation
- Server pool scaling strategy

**Retention:**
- Build expiry reminder flow
- Launch referral program (soft, no spending)

**Success Criteria:**
- Trial→paid: 5% → 10-12%
- MTFC: < 30 sec (95th)
- Server failover time: < 10 sec

**Revenue Impact:** +100% (double from baseline)

---

#### Month 3: Scale Preparation (Days 61-90)
**Theme:** Infrastructure ready for 10x

**Redis + NATS Cluster:**
- Replace single Redis with cluster
- Replace NATS single node with cluster
- Test 10-pod deployment

**China Beta:**
- shadowsocks + obfs4 protocol stack
- 5 backup domains
- 500-user beta from Singapore/HK

**Automation:**
- DevOps agent: detects + fixes 80% of issues
- Auto-scaling rules (CPU, latency-based)

**Success Criteria:**
- Multi-region deployment stable
- China beta: > 80% connection success
- Auto-fix success rate: 80%+

**Revenue Impact:** +30% (growth from new users from beta)

---

### Q2: Market Expansion + 3x Revenue

#### Month 4: China Expansion
- Full China rollout (obfuscation) — production
- MERA region beta (Middle East/North Africa)
- Multi-language onboarding (RU, EN, ZH, AR)

**Expected Users:** 100k → 200k
**Expected MRR:** $50k → $120k

---

#### Month 5: Advanced Features
- Device management (sync across phone/PC)
- Split tunneling (route some apps through VPN, others direct)
- Country selection optimization

**Expected Users:** 200k → 250k
**Expected MRR:** $120k → $180k

---

#### Month 6: Monetization
- Affiliate program (3% commission)
- Premium tier ($15/mo vs $10/mo standard)
- Family plan (5 devices, $20/mo)

**Expected Users:** 250k → 350k
**Expected MRR:** $180k → $280k

---

### Q3-Q4: Product Depth + Scale

*(Similar structure, but focused on mobile app, API, B2B partnerships)*

---

## DEPENDENCIES & CRITICAL PATH

```
┌─────────────────────────────────────────┐
│ CONVERT EXECUTION (Growth via UX)       │
├─────────────────────────────────────────┤
│  ↓ Requires: P0 fixes (Week 1)          │
│  ↓ Requires: Analytics tracking (Week 2)│
│  ↓ Dev: UX fixes + A/B testing (Week 3-4)
│  ↓ Result: 2x revenue by Day 60         │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ SCALE EXECUTION (Infrastructure)        │
├─────────────────────────────────────────┤
│  ↓ Requires: Obsv. stack (Week 2)       │
│  ↓ Requires: Auto-failover (Week 3)     │
│  ↓ Dev: Redis + NATS cluster (Week 4-6) │
│  ↓ Result: Ready for 10x (Day 90)       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ CHINA EXECUTION (Geo Expansion)         │
├─────────────────────────────────────────┤
│  ↓ Requires: Obsv. + Protocol work (W3) │
│  ↓ Requires: Localized payments (W4)    │
│  ↓ Dev: Beta launch (W5), Prod (W8)     │
│  ↓ Result: 30% revenue from CN (Month 6)│
└─────────────────────────────────────────┘
```

**Critical Path:** P0 Fixes → Observability → UX Optimization → Scale
**Timeline:** Sequential, 12 weeks for full execution

---

## SUCCESS METRICS (Monthly Tracking)

### Financial Metrics
| Month | Target MRR | Target Users | ARPU | Churn |
|-------|-----------|--------------|------|-------|
| M0 (Baseline) | $15k | 50k | $3 | Unknown |
| M1 | $15k | 50k | $3 | Track |
| M2 | $30k | 70k | $4.28 | < 5% |
| M3 | $40k | 100k | $4 | < 5% |
| M4 | $80k | 150k | $5.33 | < 5% |
| M12 | $600k | 1M | $6 | < 5% |

### Product Metrics
| Metric | M0 | M1 | M3 | M6 | M12 |
|--------|----|----|----|----|-----|
| Trial→Paid | 3% | 5% | 12% | 15% | 18% |
| MTFC (sec) | 60 | 45 | 25 | 20 | 15 |
| W1→W3 Retention | Unknown | 50% | 65% | 70% | 75% |
| Uptime | 95% | 99% | 99.5% | 99.9% | 99.95% |

### Operational Metrics
| Metric | Target |
|--------|--------|
| Auto-remediation success | 95% |
| Mean time to recovery (MTTR) | < 30 sec |
| Cost per active user/month | < $0.50 |
| On-call incidents per week | < 2 |

---

## RESOURCE ALLOCATION

### Team Structure (Recommended)
```
Product & Growth (3):
  - 1x Director (strategy, metrics, partnerships)
  - 1x Product Manager (features, A/B testing)
  - 1x Data Analyst (funnels, dashboards)

Engineering (6):
  - 1x Tech Lead (architecture, scaling)
  - 2x Backend (features, payments, China support)
  - 2x DevOps/SRE (infrastructure, automation, monitoring)
  - 1x QA/Security (testing, pen-testing for China)

Operations (1):
  - 1x Customer Success (onboarding, retention)

Total: 10 people
```

### Budget Snapshot
```
Infrastructure (month): $2k-5k
  - Servers: $2-3k
  - Observability: $500
  - CDN/DNS: $500-1k
  - Backups: $300

Team (month): $40k-60k (depending on market)

Marketing (month): $5k-10k (soft launch)
  - Community management
  - Influencer outreach
  - Paid ads (late Q2)
```

---

## RISKS & MITIGATION

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| China blocks domain | HIGH | CRITICAL | 10+ backup domains, domain fronting, custom protocol |
| Server capacity exhaustion | MEDIUM | HIGH | Auto-scaling, capacity planning, cost per user monitoring |
| Payment provider churn | MEDIUM | MEDIUM | 3+ backup providers, crypto option |
| Retention plateau | LOW | MEDIUM | Focus on onboarding QA + engagement loops |
| Tech debt accumulation | MEDIUM | MEDIUM | Weekly code review, quarterly refactoring sprints |
| Competitive pressure | MEDIUM | MEDIUM | Feature velocity, superior UX, community focus |

---

## CONCLUSION

VPNHub has all the ingredients for a category-defining product: clean tech, proven product-market fit (Telegram users want this), and a massive addressable market (Asia-Pacific demand for privacy).

**The question is execution speed.**

- **Day 30:** Stable + measurable → confidence to grow
- **Day 60:** Optimized + scaling ready → ready to spend on growth
- **Day 90:** Infrastructure bulletproof + China-ready → 10x growth possible

This roadmap is built on that momentum.

---

**Next Document:** GITHUB_ISSUES_BACKLOG.md (Epic-by-Epic issues + subtasks)
