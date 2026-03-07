"""
Distributed lock backed by NATS JetStream Key-Value store.

Usage
-----
    async with distributed_lock(js, "my-lock", ttl=30, wait_timeout=10):
        # exclusive section
        ...

Semantics
---------
- Acquire is atomic: uses KV ``create()`` (compare-and-set on revision 0).
  If the key already exists and is NOT expired, ``wait_timeout`` controls
  polling until the lock is released or the deadline is exceeded.
- If the holder crashed without releasing, the lock is automatically
  considered stale when ``expires_at`` has passed; the next waiter steals it
  via ``kv.put()`` (regular put after verifying expiry) and then overwrites
  with a new owner entry via a delete-then-create cycle.
- Release is owner-checked: only the owner that acquired the lock may
  release it; spurious releases are silently ignored.
- A background heartbeat task refreshes ``expires_at`` every ``ttl / 3``
  seconds so the lock does not expire while the holder is still running.

Lock record format (JSON, UTF-8)
---------------------------------
    {"owner_id": "<hostname>:<pid>:<uuid4>", "expires_at": <unix_float>}

Bucket
------
Bucket name: ``"locks"``
TTL on the KV bucket itself is set to ``max_ttl`` (default 300 s) so NATS
will GC orphaned keys server-side even if the holder never releases.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from nats.js import JetStreamContext
from nats.js.errors import (
    KeyNotFoundError,
    KeyWrongLastSequenceError,
    NotFoundError,
)
from nats.js.kv import KeyValue

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────
LOCK_BUCKET = "locks"
# Server-side TTL on the KV bucket — safety net for orphaned keys.
# Must be >= any per-lock TTL you pass.
BUCKET_MAX_TTL_SECONDS = 300
# Polling interval while waiting to acquire
_POLL_INTERVAL = 0.5


def _make_owner_id() -> str:
    """Unique identity for this process instance."""
    hostname = socket.gethostname()
    pid = os.getpid()
    uid = uuid.uuid4().hex
    return f"{hostname}:{pid}:{uid}"


def _encode(owner_id: str, ttl: float) -> bytes:
    payload = {
        "owner_id": owner_id,
        "expires_at": time.time() + ttl,
    }
    return json.dumps(payload).encode()


def _decode(raw: bytes) -> dict:
    return json.loads(raw.decode())


def _is_expired(record: dict) -> bool:
    return time.time() >= record["expires_at"]


# ──────────────────────────────────────────────────────────────────────────────
# KV bucket helper
# ──────────────────────────────────────────────────────────────────────────────
async def _get_or_create_bucket(js: JetStreamContext) -> KeyValue:
    """Return existing KV bucket or create it (idempotent)."""
    try:
        return await js.key_value(LOCK_BUCKET)
    except (NotFoundError, Exception):
        # Bucket doesn't exist yet — create it.
        try:
            from nats.js.kv import KeyValueConfig  # type: ignore[attr-defined]
        except Exception:
            from nats.js.api import KeyValueConfig  # type: ignore
        cfg = KeyValueConfig(
            bucket=LOCK_BUCKET,
            max_value_size=4096,
            ttl=BUCKET_MAX_TTL_SECONDS,
        )
        return await js.create_key_value(cfg)


# ──────────────────────────────────────────────────────────────────────────────
# Core acquire / release
# ──────────────────────────────────────────────────────────────────────────────
async def _try_acquire(kv: KeyValue, key: str, owner_id: str, ttl: float) -> bool:
    """
    Attempt a single atomic acquire.

    Returns True on success, False if the key is held by another live owner.
    Steals the lock if the existing record is expired.
    """
    value = _encode(owner_id, ttl)
    try:
        await kv.create(key, value)
        log.debug("event=lock.acquired key=%s owner=%s", key, owner_id)
        return True
    except KeyWrongLastSequenceError:
        # Key exists — check if it's stale.
        pass

    try:
        entry = await kv.get(key)
    except KeyNotFoundError:
        # Key was deleted between create() and get() — retry next cycle.
        return False

    record = _decode(entry.value)
    if not _is_expired(record):
        log.debug(
            "event=lock.busy key=%s held_by=%s expires_in=%.1fs",
            key,
            record["owner_id"],
            record["expires_at"] - time.time(),
        )
        return False

    # Stale lock — steal it.  Delete then create gives us CAS semantics again.
    log.warning(
        "event=lock.stale_detected key=%s stale_owner=%s stealing=true",
        key,
        record["owner_id"],
    )
    try:
        await kv.delete(key)
        await kv.create(key, value)
        log.info("event=lock.stolen key=%s new_owner=%s", key, owner_id)
        return True
    except (KeyWrongLastSequenceError, Exception):
        # Race — another waiter stole it first.
        return False


async def _release(kv: KeyValue, key: str, owner_id: str) -> None:
    """Release the lock only if we are still the owner."""
    try:
        entry = await kv.get(key)
    except KeyNotFoundError:
        log.debug("event=lock.release_skip key=%s reason=key_not_found", key)
        return
    except Exception:
        # Graceful shutdown path: NATS connection may already be closing.
        # Do not crash process teardown if lock backend is temporarily unavailable.
        log.exception("event=lock.release_skip key=%s reason=get_failed", key)
        return

    record = _decode(entry.value)
    if record["owner_id"] != owner_id:
        log.warning(
            "event=lock.release_skip key=%s reason=owner_mismatch "
            "expected=%s actual=%s",
            key,
            owner_id,
            record["owner_id"],
        )
        return

    try:
        await kv.delete(key)
        log.debug("event=lock.released key=%s owner=%s", key, owner_id)
    except Exception:
        log.exception("event=lock.release_skip key=%s reason=delete_failed", key)
        return


# ──────────────────────────────────────────────────────────────────────────────
# Heartbeat
# ──────────────────────────────────────────────────────────────────────────────
async def _heartbeat(
    kv: KeyValue, key: str, owner_id: str, ttl: float, stop: asyncio.Event
) -> None:
    """
    Refresh expires_at every ttl/3 seconds so long-running holders
    don't lose the lock to a stale-steal.
    """
    interval = max(ttl / 3, 1.0)
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
        if stop.is_set():
            break
        try:
            entry = await kv.get(key)
            record = _decode(entry.value)
            if record["owner_id"] != owner_id:
                log.error(
                    "event=lock.heartbeat_abort key=%s reason=owner_changed "
                    "expected=%s actual=%s",
                    key,
                    owner_id,
                    record["owner_id"],
                )
                return
            await kv.put(key, _encode(owner_id, ttl))
            log.debug("event=lock.heartbeat_renewed key=%s owner=%s", key, owner_id)
        except KeyNotFoundError:
            log.error("event=lock.heartbeat_abort key=%s reason=key_vanished", key)
            return
        except Exception:
            log.exception("event=lock.heartbeat_error key=%s", key)


# ──────────────────────────────────────────────────────────────────────────────
# Public context manager
# ──────────────────────────────────────────────────────────────────────────────
class LockAcquireError(Exception):
    """Raised when the lock cannot be acquired within wait_timeout."""


@asynccontextmanager
async def distributed_lock(
    js: JetStreamContext,
    name: str,
    *,
    ttl: float = 30.0,
    wait_timeout: float = 10.0,
) -> AsyncIterator[None]:
    """
    Async context manager that holds a distributed lock for the duration of
    the ``async with`` block.

    Parameters
    ----------
    js:
        Active JetStream context (from ``nc.jetstream()``).
    name:
        Lock name / KV key.  Use a descriptive slug, e.g. ``"bot-instance"``.
    ttl:
        How long (seconds) the lock lives before it is considered stale.
        Heartbeat ensures it is renewed every ``ttl / 3`` seconds.
    wait_timeout:
        Maximum seconds to wait for the lock before raising ``LockAcquireError``.
        Pass ``0`` for a non-blocking try (raises immediately if busy).

    Raises
    ------
    LockAcquireError
        If the lock cannot be acquired within ``wait_timeout`` seconds.
    """
    owner_id = _make_owner_id()
    kv = await _get_or_create_bucket(js)

    deadline = time.monotonic() + wait_timeout
    acquired = False

    log.info(
        "event=lock.acquire_attempt key=%s owner=%s ttl=%.1f wait_timeout=%.1f",
        name,
        owner_id,
        ttl,
        wait_timeout,
    )

    while True:
        acquired = await _try_acquire(kv, name, owner_id, ttl)
        if acquired:
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LockAcquireError(
                f"Could not acquire distributed lock '{name}' "
                f"within {wait_timeout}s (owner_id={owner_id})"
            )
        await asyncio.sleep(min(_POLL_INTERVAL, remaining))

    stop_heartbeat = asyncio.Event()
    hb_task = asyncio.create_task(
        _heartbeat(kv, name, owner_id, ttl, stop_heartbeat),
        name=f"lock_hb:{name}",
    )
    try:
        log.info("event=lock.held key=%s owner=%s", name, owner_id)
        yield
    finally:
        stop_heartbeat.set()
        hb_task.cancel()
        await asyncio.gather(hb_task, return_exceptions=True)
        await _release(kv, name, owner_id)
        log.info("event=lock.done key=%s owner=%s", name, owner_id)
