#!/usr/bin/env python3
"""
Distributed lock smoke test — two concurrent workers compete for the same lock.

EXPECTED BEHAVIOR
-----------------
1. Exactly one worker acquires the lock at any given time.
2. The other worker either waits (if wait_timeout > 0) or fails fast
   (if wait_timeout == 0).  This script uses wait_timeout=5 so both workers
   get a turn.
3. Critical sections do NOT overlap — verified via a shared asyncio.Event
   and a counter protected by the lock.
4. Both workers complete successfully and the final counter == 2.

USAGE
-----
    # Requires a running NATS server with JetStream enabled.
    # From repo root:
    python scripts/lock_smoke_test.py [--nats-url nats://localhost:4222]

    # Against a running compose stack:
    python scripts/lock_smoke_test.py --nats-url nats://127.0.0.1:4222

EXIT CODES
----------
    0 — all assertions passed (lock is correct)
    1 — assertion failed (mutual exclusion violated or worker error)
    2 — could not connect to NATS
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

# Adjust path so we can import the bot package from the repo root.
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import nats
except ImportError:
    print("ERROR: nats-py not installed. Run: pip install nats-py", file=sys.stderr)
    sys.exit(2)

# We import only the public API of distributed_lock.
# KeyValueConfig import lives inside the module itself.
from bot.bot.misc.distributed_lock import LockAcquireError, distributed_lock


# ──────────────────────────────────────────────────────────────────────────────
# Test state (shared between workers via asyncio — single-process, so safe)
# ──────────────────────────────────────────────────────────────────────────────
_inside_count = 0           # number of workers concurrently inside critical section
_max_concurrent = 0         # peak observed concurrency (must stay == 1)
_completions = 0            # workers that finished successfully
_violations: list[str] = [] # mutual-exclusion violation descriptions


async def worker(js, worker_id: str, lock_name: str, hold_seconds: float) -> None:
    global _inside_count, _max_concurrent, _completions

    print(f"[{worker_id}] waiting to acquire '{lock_name}'...")
    try:
        async with distributed_lock(js, lock_name, ttl=30, wait_timeout=15):
            _inside_count += 1
            concurrent = _inside_count
            _max_concurrent = max(_max_concurrent, concurrent)

            print(f"[{worker_id}] ACQUIRED — concurrent holders right now: {concurrent}")

            if concurrent > 1:
                msg = (
                    f"VIOLATION: {concurrent} workers inside critical section "
                    f"simultaneously (detected by {worker_id})"
                )
                _violations.append(msg)
                print(f"[{worker_id}] *** {msg} ***", file=sys.stderr)

            # Simulate work inside the critical section.
            await asyncio.sleep(hold_seconds)

            _inside_count -= 1
            print(f"[{worker_id}] releasing lock")

        _completions += 1
        print(f"[{worker_id}] done (completions so far: {_completions})")

    except LockAcquireError as exc:
        print(f"[{worker_id}] FAILED to acquire lock: {exc}", file=sys.stderr)
        _violations.append(f"Worker {worker_id} failed to acquire lock within timeout")


# ──────────────────────────────────────────────────────────────────────────────
# Scenario: non-blocking fail-fast (wait_timeout=0)
# ──────────────────────────────────────────────────────────────────────────────
async def test_fail_fast(js, lock_name: str) -> bool:
    """
    One worker holds the lock; a second worker with wait_timeout=0 must
    raise LockAcquireError immediately.
    """
    print("\n── test_fail_fast ──────────────────────────────────────")
    holder_ready = asyncio.Event()
    holder_done = asyncio.Event()
    result = {"second_raised": False}

    async def holder():
        async with distributed_lock(js, lock_name, ttl=30, wait_timeout=0):
            holder_ready.set()
            await holder_done.wait()

    async def challenger():
        await holder_ready.wait()
        try:
            async with distributed_lock(js, lock_name, ttl=30, wait_timeout=0):
                print("  challenger: acquired — UNEXPECTED (should have failed)", file=sys.stderr)
        except LockAcquireError:
            result["second_raised"] = True
            print("  challenger: correctly raised LockAcquireError")

    holder_task = asyncio.create_task(holder(), name="holder")
    challenger_task = asyncio.create_task(challenger(), name="challenger")

    await asyncio.gather(challenger_task)
    holder_done.set()
    await holder_task

    passed = result["second_raised"]
    print(f"  result: {'PASS' if passed else 'FAIL'}")
    return passed


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
async def main(nats_url: str) -> int:
    print("=" * 60)
    print("VPNHub Distributed Lock Smoke Test")
    print("=" * 60)
    print(f"NATS URL  : {nats_url}")
    print(f"Lock impl : bot.bot.misc.distributed_lock (JetStream KV)")
    print()

    # Connect to NATS
    try:
        nc = await nats.connect(nats_url)
        js = nc.jetstream()
        print(f"Connected to NATS at {nats_url}")
    except Exception as exc:
        print(f"ERROR: Cannot connect to NATS — {exc}", file=sys.stderr)
        return 2

    # Use a unique lock name per run so leftover keys don't interfere.
    lock_name = f"smoke-test-{int(time.time())}"

    all_passed = True

    # ── Scenario 1: Two concurrent workers, wait_timeout=15 ──────────────────
    print("\n── scenario_1: two concurrent workers (wait_timeout=15) ────")
    print("Expected: workers interleave, never overlap inside critical section")
    print()

    t0 = time.monotonic()
    await asyncio.gather(
        worker(js, "worker-A", lock_name, hold_seconds=1.0),
        worker(js, "worker-B", lock_name, hold_seconds=1.0),
    )
    elapsed = time.monotonic() - t0

    print()
    print(f"  completions     : {_completions}  (expected 2)")
    print(f"  max_concurrent  : {_max_concurrent}  (expected 1)")
    print(f"  violations      : {len(_violations)}")
    print(f"  elapsed         : {elapsed:.2f}s  (expected ≥ 2.0s — sequential holds)")

    s1_passed = (
        _completions == 2
        and _max_concurrent == 1
        and len(_violations) == 0
        and elapsed >= 1.9  # 2 × 1s holds, slight tolerance
    )
    print(f"  result          : {'PASS' if s1_passed else 'FAIL'}")
    all_passed = all_passed and s1_passed

    # ── Scenario 2: fail-fast ─────────────────────────────────────────────────
    s2_passed = await test_fail_fast(js, f"{lock_name}-failfast")
    all_passed = all_passed and s2_passed

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    if all_passed:
        print("RESULT: PASS — all assertions satisfied")
    else:
        print("RESULT: FAIL — one or more assertions violated")
        for v in _violations:
            print(f"  - {v}")

    await nc.close()
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
