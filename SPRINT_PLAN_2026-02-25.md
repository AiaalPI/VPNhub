# SPRINT PLAN 2026-02-25 (2 Weeks)

> **Canonical sprint plan.** Execution driver: `NEXT_10_EXECUTION_STEPS_2026-02-25.md`. Roadmap: `TECHNICAL_ROADMAP_2026.md`. Issues: `GITHUB_ISSUES_BACKLOG.md`.

## Supersedes SPRINT_PLAN_2026-02-24.md

`SPRINT_PLAN_2026-02-24.md` has been archived to `docs/archive/2026-02-consolidation/`.

**Why superseded:**
- The -02-24 plan covered Feb 24–Apr 20 across 4 sprints with 4-5 engineers and referenced issue IDs (#101–#802).
- This plan narrows to a single 2-week window with concrete file-level tasks and an explicit DoD.
- **Scope acceleration note:** This sprint intentionally pulls Phase 2-3 work (Prometheus/Grafana, auto-failover MVP, China smoke tests) from `TECHNICAL_ROADMAP_2026.md` Phase 2-4 into Week 1. This is an explicit decision to front-load observability and resilience. Secrets rotation (Issue #101) remains the hard prerequisite — do not start INF-1 until Step 0 in `NEXT_10_EXECUTION_STEPS_2026-02-25.md` is complete.

---

**Window:** 2026-02-25 to 2026-03-10
**Focus:** Health endpoint, observability, China smoke tests, auto-failover MVP, UX onboarding simplification
**Constraints:** 2-week execution-ready scope only

## Goals
- Ship `/health` endpoint and wire container healthchecks.
- Deliver baseline observability: request logs + `/metrics` + Prometheus/Grafana.
- Run repeatable China smoke tests from a CN proxy.
- Implement auto-failover MVP to protect users when servers go unhealthy.
- Reduce onboarding steps to key delivery in <3 taps.

## Critical Path (Execution Order)
1. INF-1 `/health` endpoint
2. INF-2 Docker healthcheck uses `/health`
3. OBS-2 `/metrics` + OBS-3 Prometheus/Grafana
4. UX-1 onboarding simplification + UX-2 fast-path `/start`
5. FO-1 detect unhealthy server + FO-2 reissue keys
6. CN-1 smoke test script + CN-2 first run and baseline

---

## Infra

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| INF-1 | Implement `/health` endpoint with DB + NATS checks (200/503) | S | None | INF-2, OBS-2 | `bot/bot/webhooks/base.py` |
| INF-2 | Add container healthcheck hitting `/health` | S | INF-1 | OBS-3, deploy readiness | `docker-compose.yml` |
| INF-3 | Add FastAPI request logging middleware (method, path, status, duration) | S | INF-1 | OBS-2 | `bot/bot/webhooks/base.py` |

## Observability

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| OBS-1 | Add Prometheus client dependency | S | None | OBS-2 | `bot/requirements.txt` |
| OBS-2 | Expose `/metrics` endpoint and basic counters (requests, errors, latency) | M | OBS-1, INF-1 | OBS-3 | `bot/bot/webhooks/base.py` |
| OBS-3 | Add Prometheus + Grafana services and config | M | OBS-2, INF-2 | Dashboards | `docker-compose.yml`, `configs/prometheus.yml` |
| OBS-4 | Add DB query timing logs for slow queries (>100ms) | M | None | Production triage | `bot/bot/database/methods/get.py`, `bot/bot/database/methods/update.py`, `bot/bot/database/methods/insert.py`, `bot/bot/database/methods/delete.py` |

## UX

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| UX-1 | Auto-select best server, remove store/location selection screens | M | None | UX-2 | `bot/bot/handlers/user/main.py`, `bot/bot/states/user.py` |
| UX-2 | Fast-path `/start` for new users to key delivery | M | UX-1 | Growth instrumentation | `bot/bot/handlers/user/keys_user.py`, `bot/bot/handlers/user/main.py` |
| UX-3 | Simplify connection instructions and add copy button | S | UX-2 | Faster activation | `bot/bot/handlers/user/keys_user.py`, `bot/bot/keyboards/inline/user_inline.py` |

## China

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| CN-1 | Add repeatable China smoke test script (curl via SOCKS proxy) | S | None | CN-2 | `scripts/china_smoke_test.sh` |
| CN-2 | Run baseline CN tests and record pass rate + latency | S | CN-1 | CN-3 | `scripts/china_smoke_test.sh`, `logs/china_smoke_2026-02-xx.log` |
| CN-3 | Add minimal retry/fallback list for CN endpoints | S | CN-2 | Ongoing CN ops | `scripts/china_smoke_test.sh` |

## Failover

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| FO-1 | Detect unhealthy servers and mark for failover events | M | None | FO-2 | `bot/bot/service/server_controll_manager.py`, `bot/bot/database/methods/update.py` |
| FO-2 | Reissue keys for users on unhealthy servers (MVP: notify + rekey on next request) | L | FO-1 | Production resilience | `bot/bot/handlers/user/edit_or_get_key.py`, `bot/bot/service/failover.py` |
| FO-3 | Admin notification + audit log for failover actions | S | FO-2 | Postmortems | `bot/bot/service/failover.py` |

## Growth

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| GR-1 | Add onboarding funnel events around `/start` and key issuance | S | UX-2 | Conversion tracking | `bot/bot/middlewares/conversion_events.py`, `bot/bot/handlers/user/keys_user.py` |

## AI Agents

| ID | Task | Effort | Depends On | Unblocks | Files |
|---|---|---|---|---|---|
| AI-0 | No AI agent experiments this sprint (de-prioritized) | S | None | None | N/A |

---

## Definition of Done (Sprint)
- `/health` returns 200 with DB + NATS healthy, 503 otherwise.
- Container healthcheck passes within 30s of startup.
- `/metrics` available and Prometheus scrapes successfully.
- Grafana dashboard online with CPU, memory, request count, error rate, DB latency.
- Onboarding: `/start` to key delivery in <3 taps, no location/store selection.
- Auto-failover MVP: users on unhealthy servers are notified and can rekey on next request.
- China smoke tests run with recorded baseline pass rate and latency.

