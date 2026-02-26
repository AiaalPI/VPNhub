"""
Lightweight DB query instrumentation for VPNHub.

Attaches SQLAlchemy engine events to log every statement execution and flag
slow queries (>= SLOW_QUERY_MS milliseconds).

Usage
-----
Call ``instrument_engine(engine)`` once after creating the async engine:

    from bot.database.db_logging import instrument_engine
    eng = create_async_engine(...)
    instrument_engine(eng)

All subsequent statement executions will be logged at DEBUG level.
Slow queries are logged at WARNING level.
Errors (raised inside execute) are already propagated by SQLAlchemy; the
caller is responsible for catching and logging them — this module only
measures timings.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)

# Queries that take longer than this are flagged as slow.
SLOW_QUERY_MS: float = 100.0

# Context-local storage for per-statement start times.
# SQLAlchemy passes a ``context`` object through cursor events; we store
# the start time there so it survives the async boundary.
_START_ATTR = "_vpnhub_query_start"


def instrument_engine(engine: AsyncEngine) -> None:
    """
    Attach timing event listeners to *engine*.

    Safe to call multiple times — SQLAlchemy deduplicates identical listeners.
    """
    sync_engine = engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        if context is not None:
            setattr(context, _START_ATTR, time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        if context is None:
            return
        start = getattr(context, _START_ATTR, None)
        if start is None:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Truncate long statements so they don't flood logs.
        stmt_preview = statement.replace("\n", " ").strip()[:200]

        if elapsed_ms >= SLOW_QUERY_MS:
            log.warning(
                "event=db.slow_query elapsed_ms=%.1f stmt=%r",
                elapsed_ms,
                stmt_preview,
            )
        else:
            log.debug(
                "event=db.query elapsed_ms=%.1f stmt=%r",
                elapsed_ms,
                stmt_preview,
            )
