import os
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import logging

from bot.webhooks.hook_wata import wata_router
from bot.webhooks.hook_yoomoney import yoomoney_router
from bot.webhooks.metrics import metrics_endpoint, prometheus_middleware

log = logging.getLogger(__name__)

# Paths that must not open a DB session (liveness probes, metrics scrape)
_NO_SESSION_PATHS = frozenset({"/healthz", "/metrics"})


@asynccontextmanager
async def lifespan(app: FastAPI):
    http_client = httpx.AsyncClient(timeout=10)
    app.state.http_client = http_client
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)


# ── Middleware: Prometheus instrumentation ────────────────────────────────────
# Registered first in source = runs last (outermost) in Starlette LIFO order,
# so it measures total wall time including session + request_id overhead.
@app.middleware("http")
async def _prometheus_middleware(request: Request, call_next):
    return await prometheus_middleware(request, call_next)


# ── Middleware: stamp every request with a unique request_id ──────────────────
# Reads X-Request-ID from incoming header if provided by an upstream proxy;
# generates a fresh UUID4 otherwise. Adds it to the response header and
# stores it in request.state so handlers and log records can reference it.
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# ── Middleware: DB session + bot injection ────────────────────────────────────
# Runs after request_id_middleware (Starlette runs middlewares LIFO).
@app.middleware("http")
async def add_common_dependencies(request: Request, call_next):
    if request.url.path in _NO_SESSION_PATHS:
        return await call_next(request)
    request.state.bot = app.state.bot
    async with app.state.session_maker() as session:
        request.state.session = session
        try:
            response = await call_next(request)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    return response


# ── Global exception handler ──────────────────────────────────────────────────
# Catches any unhandled exception that escapes a route handler.
# Returns structured JSON so callers always get a parseable error body.
# DEBUG mode (DEBUG=True env var) includes the raw exception message;
# production returns a generic string to avoid leaking internals.
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    log.exception(
        "event=unhandled_exception request_id=%s method=%s path=%s",
        req_id,
        request.method,
        request.url.path,
    )
    detail = str(exc) if os.getenv("DEBUG", "").lower() in {"1", "true", "yes"} else "internal server error"
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "request_id": req_id,
            "detail": detail,
        },
        headers={"X-Request-ID": req_id},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/healthz", include_in_schema=False)
async def healthz():
    """Liveness probe — returns 200 when the process is running."""
    return JSONResponse({"status": "ok"})


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    """Prometheus metrics scrape endpoint."""
    return await metrics_endpoint(request)


app.include_router(wata_router)
app.include_router(yoomoney_router)
