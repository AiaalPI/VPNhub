# ARCHIVED — superseded by SPRINT_PLAN_2026-02-25.md
> Date: 2026-02-26
> Reason: consolidation — same window (Feb 24–Apr 20), conflicting scope and team assumptions; -02-25 plan is authoritative.

---

# SPRINT PLAN 2026 — 4 x 2-WEEK SPRINTS

**Timeline:** Feb 24 - Mar 24, 2026 (4 weeks)
**Team:** 4-5 engineers (Backend 2, DevOps 1, Frontend 1, QA/Product 1)
**Approach:** Parallel tracks by domain + dependency gates

---

## CRITICAL PATH

```
Sprint 1 (W1-2):
  P0.1 (Secrets) ——→ blocks everything else
  ↓
  P0.2 (/health) + P0.3 (docker limits) + P0.5 (backup) ——→ unblock observability
  ↓
Sprint 2 (W3-4):
  P1.2 (DB logging) + P1.1 (exception handler) ——→ enable observability stack
  ↓
  P1.3 (HMAC validation) + AI.2 (callback validation)
  ↓
Sprint 3 (W5-6):
  P2.4 (Redis FSM) + P2.5 (Redis cache) ——→ enable scaling tests
  P1.4 (NATS worker service)
  ↓
Sprint 4 (W7-8):
  #401 (UX simplify) + #802 (A/B framework)
  #501 (Shadowsocks) + #502 (Domain rotation)
```

---

## SPRINT 1: STABILIZATION & FOUNDATIONS (Feb 24 - Mar 9)

**Goal:** Production readiness 5 → 7. Lock down all P0 blockers.

### Tasks

#### Infrastructure (DevOps Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #101 | Remove .env secrets from Git + rotate | **L (6h)** | Ready | Everything | CRITICAL: Do first day. Git history cleanup. |
| #105 | Database backup automation | **M (5h)** | Ready | #102, #201 | Daily 2 AM UTC backups, 30-day retention. |
| #103 | Docker resource limits | **S (3h)** | Ready | Load testing | Add deploy.resources to compose. |

#### Backend - Health & Exception Handling (Backend Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #102 | Implement /health endpoint | **S (3h)** | Ready | #201, K8s | DB + NATS checks, 200/503 responses. |
| #104 | Replace file lock with NATS KV | **M (5-6h)** | Ready | Multi-instance | bot/misc/nats_lock.py, update bot/run.py |
| Print removal | Remove print() statements | **S (1h)** | Ready | Code quality | grep -r "print(" bot/ |

#### QA (QA Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #801 (prep) | Review check_callbacks.py + qa.sh | **S (1h)** | Ready | PR enforcement | Verify it runs without errors. |

#### Parallel: UX Research (Product/Frontend)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| UX Readiness | Review docs/ux/fix_plan.md | **S (2h)** | Ready | Sprint 3 UX | Identify P0 UX fixes vs. nice-to-haves. |

### Sprint 1 Success Criteria

- [ ] .env removed from Git history (verified: `git log --all -p bot/.env | wc -l` → 0)
- [ ] All credentials rotated in prod + CI/CD secrets updated
- [ ] /health endpoint returns 200 (healthy), 503 (unhealthy)
- [ ] Docker healthcheck passing after 30 seconds
- [ ] Daily backups running (cron verified)
- [ ] File lock replaced with NATS KV (multi-pod K8s safe)
- [ ] Docker resource limits applied (no OOMKill on load)
- [ ] Zero unhandled print() statements in bot/
- [ ] NATS lock tested: only one bot instance starts
- [ ] No new issues in logs post-deployment

**Delivery:** Branch `feature/sprint1-stabilization` → main (requires all checks passing)

---

## SPRINT 2: OBSERVABILITY & VALIDATION (Mar 10 - Mar 23)

**Goal:** Production readiness 7 → 8. Full visibility + automated QA.

### Tasks

#### Observability Stack (Backend + DevOps)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #201 | Prometheus + Grafana setup | **M (6-8h)** | Ready | #202, #301 | docker-compose addition + /metrics endpoint. Assign: DevOps. |
| #202 | Database logging instrumentation | **L (10-12h)** | Ready | Observability | Add logging to: get.py, insert.py, update.py, delete.py. Assign: Backend. |
| #102 (finish) | Docker healthcheck validation + K8s probes | **S (1h)** | Ready | K8s deploy | livenessProbe, readinessProbe config. |

#### QA & Validation (QA Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #801 | Add callback validation to CI/CD | **S (2-3h)** | Ready | PR enforcement | GitHub Actions workflow + docs/CALLBACK_CONVENTIONS.md. |
| #202 (logging) | Slow query detection | **S (1h)** | Ready | Troubleshooting | Log queries > 100ms to warnings. |

#### Backend - Exception Handling (Backend Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #201 (prep) | Global FastAPI exception handler | **S (3.5h)** | Ready | Error visibility | Catch unhandled exceptions, log + return 500. |
| #201 (prep) | Request/response logging middleware | **S (1h)** | Ready | Tracing | Log method, path, status, duration. |

#### Payment Security (Backend)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #202 (prep) | HMAC webhook validation | **M (7h)** | Ready | Payment safety | Verify payment provider signatures before processing. |

### Sprint 2 Success Criteria

- [ ] Prometheus scraping bot metrics every 15 seconds
- [ ] /metrics endpoint returns valid Prometheus output
- [ ] Grafana dashboard accessible at http://localhost:3000 (5 panels: CPU, Memory, Requests, Errors, DB latency)
- [ ] All database methods logging (4 files completed)
- [ ] Slow query warnings appear in logs (>100ms)
- [ ] Errors logged with exc_info (full traceback)
- [ ] GitHub Actions: PR with unhandled callback → REJECTED with clear error
- [ ] PR with all callbacks handled → ACCEPTED
- [ ] Exception handler catches + logs unhandled errors
- [ ] HMAC validation passing for test payment webhooks

**Delivery:** Branch `feature/sprint2-observability` → main

---

## SPRINT 3: SCALING & MULTI-INSTANCE (Mar 24 - Apr 6)

**Goal:** Enable horizontal scaling. Production readiness 8 → 9.

### Tasks

#### Infra: NATS & Redis (DevOps Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #301 (prep) | Separate NATS worker service | **M (7h)** | Ready | #302 | NATS consumers on dedicated pod. Update docker-compose. |
| #601 (prep) | Redis Cluster evaluation | **S (3h)** | Ready | #401, scaling | Decide: Cluster vs. Sentinel vs. single + replication. |

#### Auto-Failover MVP (Backend Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #301 | Server health monitor | **L (8-10h)** | Ready | #302 | bot/misc/server_health_check.py. Ping + latency + packet loss. |
| #302 | Key reassignment service | **M (6-8h)** | Ready | Resilience | Detect unhealthy → reassign users → notify. |
| #103 (verify) | Circuit breaker pattern | **S (2h)** | Ready | Cascading failure prevention | Payment provider timeout handling. |

#### UX MVP (Frontend + Backend)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #401 (MVP) | Auto-server selection (no manual location pick) | **M (3-4h)** | Ready | Conversion | Remove store selection screen. Fast path: /start → key. |
| #401 (MVP) | Payment method selector (show 3 options) | **S (2h)** | Ready | Conversion | Stripe + PayPal + Crypto buttons. |

#### AI/QA (QA Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #802 (prep) | A/B experiment framework setup | **S (2h)** | Ready | Growth | bot/bot/misc/experiments.py + ExperimentManager class. |

### Sprint 3 Success Criteria

- [ ] Health check service running, detecting unhealthy servers within 30 seconds
- [ ] Unhealthy server automatically removed from DNS/LB
- [ ] User keys automatically reassigned to healthy server
- [ ] Users notified of reassignment via Telegram
- [ ] Failover tested: simulate server down → key moved → user reconnects
- [ ] Zero data loss during reassignment (db audit)
- [ ] /start → auto-select best server → key delivered (no intermediate screens)
- [ ] Payment method selector shows 3+ options
- [ ] Conversion rate measured for UX changes (baseline: 3-5%)
- [ ] Experiment framework tested: consistent user bucketing (A/A test passes)
- [ ] NATS worker service on separate pod (docker-compose)
- [ ] Circuit breaker prevents cascading failures

**Delivery:** Branch `feature/sprint3-scaling` → main

---

## SPRINT 4: GROWTH & CHINA READINESS (Apr 7 - Apr 20)

**Goal:** Enable growth levers. China market MVP.

### Tasks

#### China Market (Backend + DevOps)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #501 | Shadowsocks protocol implementation | **M (3h)** | Ready | China expansion | bot/bot/service/vpn/protocols/shadowsocks.py. |
| #502 | Backup domains + client rotation | **S (2-3h)** | Ready | Resilience | Register 5 domains, DNS round-robin, client failover logic. |
| #501 (test) | Test from CN IP (simulated DPI) | **M (4h)** | Ready | Validation | >80% success rate, <200ms latency. |

#### Growth: Conversion Experiments (Product + Frontend)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| #802 | Launch onboarding_copy A/B test | **S (2h)** | Ready | Growth | 90-10 split (control vs. urgent). Monitor conversion. |
| #302 (finish) | Trial expiry alerts | **S (3-4h)** | Ready | Retention | Schedule daily checker at 2 AM. Send alerts 3/7/14 days before expiry. |
| #401 (finish) | Multi-device support (1 plan = 3 devices) | **M (5h)** | Ready | Upsell | DB migration, device_uuid column, UI to add/remove devices. |

#### Final QA (QA Lead)

| ID | Task | Effort | Status | Blocks | Notes |
|----|------|--------|--------|--------|-------|
| Integration | End-to-end testing: /start → payment → connected | **M (4h)** | Ready | Release | Emoji: new user flow, existing user reconnect, multi-device. |

### Sprint 4 Success Criteria

- [ ] Shadowsocks protocol available in protocol selector
- [ ] obfs4 (if added) tested from CN IP
- [ ] Backup domains accessible + DNS failover working
- [ ] Client rotates domain on failure (logs show domain.failover events)
- [ ] A/B test running: onboarding_copy at 10% traffic
- [ ] Conversion rate by variant tracked
- [ ] Trial expiry alerts sent at correct times
- [ ] Users can add up to 3 devices per plan
- [ ] Device management UI working (add/remove)
- [ ] End-to-end tests passing (new user flow + existing user + multi-device)
- [ ] Zero new bugs in production logs
- [ ] Business metrics tracked: conversion %, retention %, ARPU

**Delivery:** Branch `feature/sprint4-growth` → main + Release to production

---

## SPRINT BURN-DOWN BY EFFORT

### Expected Team Allocation

**Backend Lead (2 engineers):**
- Sprint 1: #104 (NATS lock), print removal, #102 micro
- Sprint 2: #202 (10-12h split), #201 exception handling, #202 HMAC
- Sprint 3: #301 (8-10h), #302 (6-8h)
- Sprint 4: #501 shadowsocks (3h), #401 UX (3-4h), Integration (4h)

**DevOps Lead (1 engineer):**
- Sprint 1: #101 (6h), #105 (5h), #103 (3h) — 14h total
- Sprint 2: #201 (6-8h) — 8h total
- Sprint 3: #301 worker service (7h), #601 eval (3h) — 10h total
- Sprint 4: #501 testing (4h) — 4h total

**QA/Product Lead (1 engineer):**
- Sprint 1: #801 prep (1h), UX research (2h) — 3h total
- Sprint 2: #801 CI/CD (2-3h) — 3h total
- Sprint 3: #802 prep (2h) — 2h total
- Sprint 4: Integration (4h) — 4h total

**Frontend (share with Product on UX):**
- Sprint 3: #401 UX updates (3-4h) — 4h total
- Sprint 4: #302 expiry alerts (3-4h), #401 multi-device (5h) — 9h total

---

## DEPENDENCIES & GATES

### Gate 1: End of Sprint 1 (March 9)
**Decision:** Can we deploy to production?
- [ ] Secrets fully rotated + verified
- [ ] File lock replaced (K8s-safe)
- [ ] /health endpoint working
- [ ] Daily backups running
**Go/No-Go:** YES → Proceed. NO → Hold Sprint 2, fix P0 issues.

### Gate 2: End of Sprint 2 (March 23)
**Decision:** Do we have observability?
- [ ] Prometheus + Grafana working
- [ ] All queries logged with duration
- [ ] Slow query detection active
- [ ] GitHub Actions CI/CD enforcing callback validation
**Go/No-Go:** YES → Multi-instance safe. NO → Halt Sprint 3, fix observability.

### Gate 3: End of Sprint 3 (April 6)
**Decision:** Can we scale horizontally?
- [ ] Health check detecting failures in <30 sec
- [ ] Auto-reassignment working
- [ ] UX simplification tested (baseline conversion measured)
- [ ] A/B framework tested
**Go/No-Go:** YES → Growth mode. NO → Iterate, don't launch Sprint 4.

### Gate 4: End of Sprint 4 (April 20)
**Decision:** Can we ship to production?
- [ ] China smoke tests passing (80%+ success)
- [ ] A/B test showing direction (even if no lift)
- [ ] Zero critical bugs in logs
- [ ] Runbooks for ops team updated
**Go/No-Go:** YES → Deploy to production. NO → Fix issues, iterate.

---

## CRITICAL SUCCESS FACTORS

1. **Sprint 1 is non-negotiable.** P0.1 (secrets) blocks everything else. Do it first.
2. **Respect dependencies.** Don't start #301 until #102 + #201 complete (need healthcheck + observability to detect failures).
3. **Test early, test often.** Each sprint: integration test at end.
4. **Measure conversion.** Sprint 3 UX changes → baseline. Sprint 4 A/B → lift.
5. **Document decisions.** Each sprint: update runbook with new operational procedures.

---

## REWORK RISK MITIGATION

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Git history cleanup takes longer than 6h | Medium | Pre-script the git filter-branch command. Test on staging first. |
| Prometheus cardinality explosion | Low | Define label limits upfront. Use job agent for metrics cleanup. |
| NATS rebalancing creates lag | Medium | Test with 1000 message backlog. Monitor consumer lag during transition. |
| Failover test exposes race condition | Medium | Run failover test in staging 3x before production. |
| China DPI detection bypassed quickly | Low | Rotate protocols monthly. Monitor success rate continuously. |

---

## POST-SPRINT 4 ROADMAP (NOT IN THIS PLAN)

- **Week 9-10:** Redis Cluster (full HA, not just eval)
- **Week 11-12:** NATS Cluster setup
- **Week 13-16:** Multi-region deployment
- **Week 17-20:** DevOps automation agent (if time allows)
- **Ongoing:** Monthly A/B experiments (3+ per month minimum)

---

## SUCCESS METRICS AT END OF SPRINT 4

| Metric | Current | Target | Owner |
|--------|---------|--------|-------|
| Production Readiness Score | 5/10 | 9/10 | Engineering |
| Uptime | 95% | 99.5%+ | DevOps |
| Trial→Paid Conversion | 3-5% | 8-12% | Product |
| Mean Time To Recovery (MTTR) | 30 min | <5 min | DevOps |
| Unhandled Callbacks in PRs | High | 0 | QA |
| China User Success Rate | 0% | >80% | Backend |
| WAU (estimated) | 50k | 75k+ | Product |
| MRR (estimated) | $15k | $40k+ | Finance |

---

##CRITICAL PATH SUMMARY (10 lines max)

1. **Week 1:** Rotate credentials (#101) → foundation for everything
2. **Week 1-2:** Health endpoint (#102) + backups (#105) + NATS lock (#104)
3. **Week 2-3:** Observability stack (#201, #202) → enable multi-instance
4. **Week 3-4:** Auto-failover MVP (#301, #302) → reliability foundation
5. **Week 3-4:** UX simplification (#401) + A/B framework (#802) → growth
6. **Week 5:** Shadowsocks + backup domains (#501, #502) → China market
7. **Week 5:** Launch A/B experiment → measure conversion baseline
8. **Week 6:** Multi-device support (#401) → upsell trigger
9. **Week 7:** End-to-end testing + go-live readiness
10. **Gate checks:** P0 blocks → observability → scaling → growth. No deps skipped.
