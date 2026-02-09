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
- [ ] Add admin alerts throttling
- [ ] Document common failure scenarios in `runbook.md`

---

## 🟣 EPIC 4 — Tests & CI (P2)

Goal: prevent regressions.

- [ ] Add basic tests for `Config`
- [ ] Test NATS config parsing
- [ ] Add `pytest` instructions
- [ ] Add GitHub Actions CI:
  - install deps
  - syntax check
  - tests

---

## ⚫ EPIC 5 — Future Improvements (BACKLOG)

- [ ] Replace APScheduler with task queue (optional)
- [ ] Separate FastAPI into own service
- [ ] Add metrics (Prometheus / simple counters)
- [ ] Prepare multi-region NATS

---

## 📌 How Codex should use this file

- Read this file before making changes
- Work on **one unchecked task at a time**
- Never skip tasks
- After completing a task, update this file and mark it `[x]`