# XUI Subscription Healing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure a paid/free-day extension restores the 3x-ui panel-side client so users with active days can actually connect.

**Architecture:** Add a small service that heals panel-side VPN clients after subscription mutations. The service logs structured events, only touches supported panel types, and is called by all existing subscription extension paths.

**Tech Stack:** Python, aiogram service layer, SQLAlchemy models, pyxui-async, pytest, Docker build gate.

---

### Task 1: Add XUI Healing Tests

**Files:**
- Modify: `tests/test_trial_payments.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:
- `extend_subscription()` calls `restore_panel_client_access()` for an existing key.
- `extend_subscription()` calls `restore_panel_client_access()` for a newly created key.
- `restore_panel_client_access()` logs and returns `skipped` when key has no server.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `pytest tests/test_trial_payments.py -q`

Expected: at least one new test fails because `restore_panel_client_access` does not exist yet.

### Task 2: Implement Panel Healing Service

**Files:**
- Create: `bot/bot/services/panel_healing_service.py`
- Modify: `bot/bot/misc/VPN/ServerManager.py`
- Modify: `bot/bot/misc/VPN/Xui/XuiBase.py`

- [ ] **Step 1: Add `PanelHealResult`**

Create a dataclass with fields:
- `status: str`
- `key_id: int | None`
- `user_id: int | None`
- `server_id: int | None`
- `email: str | None`
- `details: str | None = None`

- [ ] **Step 2: Add XUI restore primitive**

Add `XuiBase.restore_client_access(email: str, limit_gb: int | None = None)` that:
- loads the client;
- returns `missing` if it does not exist;
- calls `update_client(... enable=True, total_gb=<bytes>)`;
- calls `reset_client_traffic(...)`;
- logs success/failure with `event=xui_client_restore`.

Use `CONFIG.limit_GB` when positive, otherwise use `1000 GB` as the defensive default. Convert GB to bytes before calling `pyxui_async.update_client`.

- [ ] **Step 3: Add manager wrapper**

Add `ServerManager.restore_client_access(name, key_id, limit_gb=None)` that builds the standard email and delegates to XUI clients that support restore.

- [ ] **Step 4: Add service entrypoint**

Implement `restore_panel_client_access(session, key, reason, limit_gb=None)`:
- skip if key/server is missing;
- skip unsupported server types cleanly;
- login to panel;
- call manager restore;
- log `event=panel_client_restore`.

### Task 3: Wire Healing Into Subscription Mutations

**Files:**
- Modify: `bot/bot/services/subscription_mutation_service.py`
- Modify: `bot/bot/database/methods/update.py`
- Test: `tests/test_trial_payments.py`

- [ ] **Step 1: Wire `extend_subscription`**

After a new or existing key is committed, call `restore_panel_client_access(session, key, reason=reason)`.

- [ ] **Step 2: Wire legacy mutation helpers**

Call the same service after `add_time_person`, `add_time_key`, and `new_time_key` commit successfully.

- [ ] **Step 3: Verify tests pass**

Run: `pytest tests/test_trial_payments.py -q`

Expected: pass.

### Task 4: Add Operator Audit Script

**Files:**
- Create: `scripts/audit_xui_active_clients.py`

- [ ] **Step 1: Create dry-run audit**

The script runs inside `vpn_hub_bot` and prints active DB keys against panel status:
- active key count;
- panel client exists;
- enabled;
- used GB;
- limit GB;
- exhausted;
- suggested action.

- [ ] **Step 2: Add optional apply mode**

With `--apply`, call `restore_panel_client_access()` for disabled, exhausted, or missing active keys.

- [ ] **Step 3: Verify script syntax**

Run: `python3 -m py_compile scripts/audit_xui_active_clients.py`

Expected: no output.

### Task 5: Archive Old Assets And Local Logs

**Files:**
- Move: `bot/bot/img/*_before_ysyakh_*` to `docs/archive/2026-06-ysyakh-assets/`
- Move: `.playwright-cli/console-2026-03-19T05-28-51-890Z.log` to `docs/archive/2026-06-local-logs/`
- Move: `logs/all.log` and `logs/errors.log` to `docs/archive/2026-06-local-logs/`
- Create: `docs/ops/2026-06-26-xui-healing-log.md`

- [ ] **Step 1: Archive only obvious stale files**

Move backup images and local generated logs into archive directories. Do not delete final bot assets.

- [ ] **Step 2: Write operations log**

Record root cause, production one-off fix, code fix, archive list, and verification commands.

### Task 6: Build Gate

**Files:**
- Existing project files only.

- [ ] **Step 1: Run focused tests**

Run: `pytest tests/test_trial_payments.py -q`

Expected: pass.

- [ ] **Step 2: Run localization compile/build gate**

Run: `docker compose build vpn_hub_bot`

Expected: pass.

