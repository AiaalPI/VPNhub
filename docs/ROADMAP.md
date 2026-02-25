# ARCHIVED — superseded by TECHNICAL_ROADMAP_2026.md
> Date: 2026-02-26
> Reason: consolidation — this file claimed canonical authority but is stale (stuck at EPIC 5, sequential Codex model). Canonical roadmap is `TECHNICAL_ROADMAP_2026.md`.

---

# VPNHub — Project Roadmap (Codex-driven)

This roadmap is the **single source of truth** for project progress.
All tasks are designed to be executed incrementally using Codex / Copilot Chat.

Rules:
- Tasks are completed **top-down**
- Each task must be atomic
- No task should change runtime behavior unless explicitly stated
- After completing a task, mark it as `[x]`

---

## 🟢 EPIC 0 — Repository & Documentation (FOUNDATION)

- [x] Initialize Git repository
- [x] Add `.gitignore`
- [x] Add `README.md`
- [x] Add `CHANGELOG.md`
- [x] Create `docs/` directory
- [x] Add `docs/project_rules.md`
- [x] Add `docs/architecture.md`
- [x] Add `docs/env.md`
- [x] Add `docs/runbook.md`

---

## 🟡 EPIC 1 — Configuration Hardening (P0 – SAFE)

Goal: make configuration strict, typed, predictable.

- [x] Document `NATS_SERVERS` in `docs/env.md`
- [x] Refactor `Config` to support `NATS_SERVERS` as `list[str]`
- [x] Keep `NATS_URL` as legacy fallback
- [x] Remove duplicated config fields (`id_channel`, `link_channel`)
- [x] Enforce correct types:
  - `id_channel: int`
  - `month_cost: list[int]`
- [x] Add helper: `parse_csv_urls()`
- [x] Ensure `connect_to_nats(CONFIG.nats_servers)` works unchanged
- [x] Update docs after config refactor

---

## 🟠 EPIC 2 — Runtime Stability & Performance (P1)

Goal: reduce load, prevent freezes, isolate heavy operations.

- [x] Optimize `loop()` (remove heavy server calls)
- [x] Move server space recalculation to `server_control_manager`
- [x] Ensure `delete_key()` only publishes NATS events
- [x] Add protection against slow server responses
 - [x] Add logging around critical background jobs

---

## 🔵 EPIC 3 — Observability & Safety (P1)

Goal: understand system state at any moment.

- [x] Add structured logging for:
  - [x] subscriptions expiry
  - [x] server availability
  - [x] NATS publish/consume
- [x] Add admin alerts throttling
- [x] Document common failure scenarios in `runbook.md`

---

## 🟣 EPIC 4 — Tests & CI (P2) — ✅ DONE

Goal: prevent regressions.

**Delivered:**
- [x] Add `tests/test_basic.py` smoke test: verifies `CONFIG` loads with minimal env stubs
- [x] Create `pytest.ini` with test discovery config
- [x] Add `.github/workflows/ci.yml` GitHub Actions workflow:
  - Triggers on push/PR to main
  - Sets up Python 3.11
  - Installs `bot/requirements.txt`
  - Runs `python -m compileall -q bot` for syntax check
  - Runs `pytest` test suite
- [x] Actions green: all tests pass, no compile errors

---

## 🟠 EPIC 5 — Trial Period & Subscription Lifecycle (P1)

Goal: deliver a complete, testable trial flow and subscription management with safe payment integration.

**Trial Period Activation & Rules:**
- [ ] Document trial rules in `docs/env.md`:
  - Trial duration (from `TRIAL_PERIOD`)
  - Eligibility conditions (first-time users only)
  - Auto-expiry behavior
  - Trial-to-paid conversion flow
- [ ] Implement trial activation handler:
  - Set `Keys.trial_period = True` + `Persons.trial_period = True`
  - Record activation timestamp (add field if needed)
  - Log activation with structured logging
- [ ] Test trial edge cases:
  - User cannot activate trial twice
  - Trial expires correctly after period ends
  - Expired trial key is revoked cleanly

**Subscription Lifecycle:**
- [ ] Formalize subscription state machine:
  - States: `active`, `expiring_soon`, `expired`, `extended`
  - Transitions: create → active → expiring_soon → expired OR extend → active
- [ ] Implement extension logic:
  - User extends active subscription
  - Extend only if not already extended this period
  - Log extension with old + new expiry dates
- [ ] Add background job for expiry detection:
  - Scan for keys expiring in 24h, send alert to user
  - Scan for expired keys, set `work = False` if needed
  - Publish NATS event for async key removal
- [ ] Test lifecycle with mocked time (freeze_gun or similar)

**Payments Integration (One Provider End-to-End):**
- [ ] Choose: YooKassa or Cryptomus (based on fewest deps)
- [ ] Wire payment provider:
  - Create payment order with correct amount + months
  - Handle webhook: verify signature, mark payment as confirmed
  - Link payment ID to `Keys.id_payment`
- [ ] On payment confirmation:
  - Calculate expiry: `now + (months * MONTH_COST_SECONDS)`
  - Update `Keys.subscription` with new expiry epoch
  - Log payment with structured logging (user_id, amount, months, expiry)
- [ ] Test payment flow with mock webhooks
- [ ] Handle edge cases:
  - Duplicate webhook (idempotent)
  - Payment timeout (user retries)
  - Multiple partial payments

**Observability & Safe Rollback:**
- [ ] Add structured logging:
  - Trial activation/expiry events
  - Payment confirmation (including provider, amount, months)
  - Subscription state transitions
- [ ] Add metrics:
  - Active trials count
  - Active subscriptions count by age
  - Failed payment attempts by provider
- [ ] Add admin dashboard queries (see `docs/runbook.md`):
  - Query: "Find users with expiring keys (next 24h)"
  - Query: "Find failed payments this week"
  - Query: "Find orphaned keys (payment ID missing)"
- [ ] Implement graceful rollback:
  - If payment webhook fails: retry with backoff, log error
  - If trial-to-paid fails: revert to active trial, alert admin
  - If key removal fails: mark for manual review

**Acceptance Criteria:**
- [ ] Trial period fully testable: 100% coverage of `test_trial_lifecycle.py`
- [ ] One payment provider is wired and confirmed with mock tests
- [ ] All subscription state transitions are logged and queryable
- [ ] No orphaned keys or payments in database after full flow
- [ ] Rollback scenarios tested and documented in `docs/runbook.md`

**Out of Scope:**
- Multi-provider payment reconciliation (future EPIC)
- Subscription pausing / resumption
- Prorated refunds
- Auto-renewal with multiple retry logic (v2)
- Metrics dashboards (use Prometheus later)

---

## 🔮 EPIC 6 — Future Improvements (BACKLOG)

- [ ] Replace APScheduler with task queue (optional, after EPIC 5 migration)
- [ ] Separate FastAPI metrics endpoint into own service
- [ ] Add Prometheus integration for fine-grained observability
- [ ] Prepare multi-region NATS with stream cross-replication
- [ ] Payment provider abstraction layer (strategy pattern)

---

## 📌 How Codex should use this file

- Read this file before making changes
- Work on **one unchecked task at a time**
- Never skip tasks
- After completing a task, update this file and mark it `[x]`