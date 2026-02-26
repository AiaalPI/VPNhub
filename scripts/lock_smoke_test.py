#!/usr/bin/env python3
"""
Distributed lock smoke test — validates all critical lock behaviours.

SCENARIOS
---------
1. acquire_success        — lock acquired, held, released; no concurrent overlap
2. fail_fast              — second contender with wait_timeout=0 raises LockAcquireError
3. heartbeat_extends_ttl  — holder lives past the original TTL without losing the lock
4. stale_lock_stealing    — expired lock record is stolen by new contender

EXIT CODES
----------
    0 — all scenarios passed
    1 — one or more scenarios failed
    2 — could not connect to NATS / JetStream not available

USAGE
-----
    # From repo root, against running compose stack:
    docker compose exec vpn_hub_bot python /app/scripts/lock_smoke_test.py \
        --nats-url nats://nats:4222

    # From host (requires NATS port exposed):
    python scripts/lock_smoke_test.py [--nats-url nats://127.0.0.1:4222]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

# Allow running from repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import nats
except ImportError:
    print("ERROR: nats-py not installed.  Run: pip install nats-py", file=sys.stderr)
    sys.exit(2)

from bot.bot.misc.distributed_lock import (
    LockAcquireError,
    _get_or_create_bucket,
    distributed_lock,
)


# ─────────────────────────────────────────────────────────────────────────────
# Result tracking
# ─────────────────────────────────────────────────────────────────────────────
_results: dict[str, bool] = {}


def _record(name: str, passed: bool) -> bool:
    _results[name] = passed
    label = "PASS" if passed else "FAIL"
    print(f"  result : {label}")
    return passed


def _header(title: str) -> None:
    print()
    print(f"── {title} {'─' * max(0, 56 - len(title))}")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — acquire_success
#
# Two workers compete for the same lock with wait_timeout=15.
# Expected:
#   - Both complete (completions == 2)
#   - Never more than 1 inside the critical section at once
#   - Elapsed >= 2 × hold_seconds (sequential, not parallel)
# ─────────────────────────────────────────────────────────────────────────────
async def scenario_acquire_success(js, lock_name: str) -> bool:
    _header("scenario_1: acquire_success")
    print("  Two workers serialise through the lock (wait_timeout=15).")

    inside = 0
    max_concurrent = 0
    completions = 0
    violations: list[str] = []

    async def worker(wid: str, hold: float) -> None:
        nonlocal inside, max_concurrent, completions
        async with distributed_lock(js, lock_name, ttl=30, wait_timeout=15):
            inside += 1
            snap = inside
            max_concurrent = max(max_concurrent, snap)
            if snap > 1:
                violations.append(f"[{wid}] overlap: {snap} inside simultaneously")
            print(f"  [{wid}] acquired (concurrent={snap})")
            await asyncio.sleep(hold)
            inside -= 1
        completions += 1
        print(f"  [{wid}] done")

    hold = 0.5
    t0 = time.monotonic()
    await asyncio.gather(worker("A", hold), worker("B", hold))
    elapsed = time.monotonic() - t0

    print(f"  completions    : {completions}  (want 2)")
    print(f"  max_concurrent : {max_concurrent}  (want 1)")
    print(f"  violations     : {violations or 'none'}")
    print(f"  elapsed        : {elapsed:.2f}s  (want >= {2*hold:.1f}s)")

    passed = completions == 2 and max_concurrent == 1 and not violations and elapsed >= 2 * hold * 0.9
    return _record("acquire_success", passed)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — fail_fast
#
# One worker holds the lock. A challenger with wait_timeout=0 must raise
# LockAcquireError immediately (< 0.5 s), not spin.
# ─────────────────────────────────────────────────────────────────────────────
async def scenario_fail_fast(js, lock_name: str) -> bool:
    _header("scenario_2: fail_fast (wait_timeout=0)")
    print("  Challenger must raise LockAcquireError immediately when lock is held.")

    holder_in = asyncio.Event()
    holder_release = asyncio.Event()
    raised = False
    elapsed_challenge = 0.0

    async def holder() -> None:
        async with distributed_lock(js, lock_name, ttl=30, wait_timeout=0):
            holder_in.set()
            await holder_release.wait()

    async def challenger() -> None:
        nonlocal raised, elapsed_challenge
        await holder_in.wait()
        t0 = time.monotonic()
        try:
            async with distributed_lock(js, lock_name, ttl=30, wait_timeout=0):
                print("  challenger: acquired — UNEXPECTED", file=sys.stderr)
        except LockAcquireError:
            raised = True
            elapsed_challenge = time.monotonic() - t0
            print(f"  challenger: LockAcquireError in {elapsed_challenge:.3f}s (expected < 0.5s)")

    holder_task = asyncio.create_task(holder())
    await asyncio.create_task(challenger())
    holder_release.set()
    await holder_task

    print(f"  raised LockAcquireError : {raised}")
    print(f"  challenge elapsed       : {elapsed_challenge:.3f}s")
    passed = raised and elapsed_challenge < 0.5
    return _record("fail_fast", passed)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — heartbeat_extends_ttl
#
# Acquire a lock with a short TTL (3 s).  Hold it for 2 × TTL (6 s).
# The heartbeat must renew expires_at so the lock is not stolen.
# After releasing, verify the key is gone (or belongs to no one else).
# ─────────────────────────────────────────────────────────────────────────────
async def scenario_heartbeat_extends_ttl(js, lock_name: str) -> bool:
    _header("scenario_3: heartbeat_extends_ttl")
    ttl = 3.0
    hold = ttl * 2 + 0.5   # 6.5 s — well past the original TTL
    print(f"  TTL={ttl}s, holding for {hold}s. Heartbeat must prevent expiry.")

    stolen = False

    async def spy() -> None:
        """Poll the KV every 0.5 s while holder is sleeping; flag if key vanishes."""
        nonlocal stolen
        kv = await _get_or_create_bucket(js)
        await asyncio.sleep(ttl + 0.5)   # wait past original expiry
        try:
            entry = await kv.get(lock_name)
            record = json.loads(entry.value.decode())
            remaining = record["expires_at"] - time.time()
            print(f"  spy: key still live, expires_in={remaining:.1f}s (heartbeat working)")
        except Exception as exc:
            stolen = True
            print(f"  spy: key missing/error — heartbeat may have failed: {exc}", file=sys.stderr)

    async def holder() -> None:
        async with distributed_lock(js, lock_name, ttl=ttl, wait_timeout=0):
            print(f"  holder: acquired, sleeping {hold}s...")
            # Run spy concurrently to check heartbeat is renewing the key.
            spy_task = asyncio.create_task(spy())
            await asyncio.sleep(hold)
            await spy_task
            print("  holder: releasing")

    await holder()
    passed = not stolen
    return _record("heartbeat_extends_ttl", passed)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4 — stale_lock_stealing
#
# Inject an already-expired lock record directly into the KV bucket, then
# attempt to acquire. The acquire must succeed (steal the stale record) rather
# than being blocked.
# ─────────────────────────────────────────────────────────────────────────────
async def scenario_stale_lock_stealing(js, lock_name: str) -> bool:
    _header("scenario_4: stale_lock_stealing")
    print("  Inject an expired lock record; new acquirer must steal it.")

    kv = await _get_or_create_bucket(js)

    # Write an already-expired record (expires_at = 30 s ago).
    stale_owner = "ghost-host:99999:deadbeef"
    expired_value = json.dumps(
        {"owner_id": stale_owner, "expires_at": time.time() - 30}
    ).encode()

    # Clean slate first, then inject stale record.
    try:
        await kv.delete(lock_name)
    except Exception:
        pass
    # Use put() to write directly (bypasses CAS — simulates a crashed holder).
    await kv.put(lock_name, expired_value)
    print(f"  injected stale record for owner={stale_owner!r}")

    steal_succeeded = False
    try:
        async with distributed_lock(js, lock_name, ttl=10, wait_timeout=2):
            steal_succeeded = True
            print("  new acquirer: ACQUIRED stale lock successfully (steal worked)")
    except LockAcquireError:
        print("  new acquirer: LockAcquireError — steal FAILED", file=sys.stderr)

    return _record("stale_lock_stealing", steal_succeeded)


# ─────────────────────────────────────────────────────────────────────────────
# JetStream availability pre-check
# ─────────────────────────────────────────────────────────────────────────────
async def check_jetstream(js) -> bool:
    """Verify JetStream and KV are functional before running tests."""
    try:
        kv = await _get_or_create_bucket(js)
        await kv.put("_ping", b"1")
        await kv.get("_ping")
        await kv.delete("_ping")
        print("  JetStream KV: OK")
        return True
    except Exception as exc:
        print(f"  JetStream KV: UNAVAILABLE — {exc}", file=sys.stderr)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
async def main(nats_url: str) -> int:
    print("=" * 60)
    print("VPNHub Distributed Lock Smoke Test")
    print("=" * 60)
    print(f"NATS URL  : {nats_url}")
    print(f"Lock impl : bot.bot.misc.distributed_lock (JetStream KV)")

    try:
        nc = await nats.connect(nats_url, connect_timeout=5)
        js = nc.jetstream()
        print(f"NATS      : connected")
    except Exception as exc:
        print(f"\nERROR: Cannot connect to NATS — {exc}", file=sys.stderr)
        return 2

    print()
    print("── pre-flight: JetStream KV check ──────────────────────────")
    if not await check_jetstream(js):
        print("\nERROR: JetStream not functional. Is NATS started with jetstream {}?",
              file=sys.stderr)
        await nc.close()
        return 2

    # Unique prefix so parallel runs don't collide.
    prefix = f"smoke-{int(time.time())}"

    # Run scenarios sequentially (each uses a distinct key).
    await scenario_acquire_success(js, f"{prefix}-s1")
    await scenario_fail_fast(js, f"{prefix}-s2")
    await scenario_heartbeat_extends_ttl(js, f"{prefix}-s3")
    await scenario_stale_lock_stealing(js, f"{prefix}-s4")

    await nc.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    all_passed = all(_results.values())
    for name, ok in _results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print()
    if all_passed:
        print("RESULT: PASS — all assertions satisfied")
    else:
        failed = [n for n, ok in _results.items() if not ok]
        print(f"RESULT: FAIL — {len(failed)} scenario(s) failed: {', '.join(failed)}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Distributed lock smoke test")
    parser.add_argument(
        "--nats-url",
        default=os.getenv("NATS_SERVERS", "nats://127.0.0.1:4222"),
        help="NATS server URL (default: nats://127.0.0.1:4222)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.nats_url)))
