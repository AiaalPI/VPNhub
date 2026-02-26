"""
Prometheus metrics for the VPNHub FastAPI app.

Exposes /metrics in the text format that Prometheus scrapes.

Metrics
-------
http_requests_total{method, path, status}   Counter
http_request_duration_seconds{method, path} Histogram  (buckets: 5ms–30s)

The middleware is registered in base.py.  /metrics itself is excluded from
the DB-session middleware via _NO_SESSION_PATHS so it is always fast.
"""

from __future__ import annotations

import time

from fastapi import Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# ── Metric definitions ────────────────────────────────────────────────────────
# Labels are kept minimal to avoid high-cardinality explosions.
# 'path' uses the route template (e.g. /payments/wata/webhook), not the raw URL.

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 30.0),
)


# ── Scrape endpoint ───────────────────────────────────────────────────────────
async def metrics_endpoint(request: Request) -> Response:
    """Return Prometheus text exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Instrumentation middleware ────────────────────────────────────────────────
async def prometheus_middleware(request: Request, call_next):
    """
    Measure every request and update REQUEST_COUNT + REQUEST_LATENCY.

    Uses the matched route path template when available so dynamic path
    segments (e.g. /users/123) are collapsed to /users/{user_id}.
    Falls back to request.url.path for unmatched routes (404s, /metrics).
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    # Use the route template to avoid label explosion on dynamic segments.
    route = request.scope.get("route")
    path = route.path if route else request.url.path

    method = request.method
    status = str(response.status_code)

    REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
    REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)

    return response
