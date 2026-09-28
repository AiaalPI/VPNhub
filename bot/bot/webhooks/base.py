import os
import uuid
import base64
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
import logging
from sqlalchemy import text

from bot.database.methods.get import get_key_id
from bot.services.clash_subscription_service import build_clash_config
from bot.services.singbox_subscription_service import build_singbox_config
from bot.services.subscription_service import (
    parse_clean_subscription_token,
    render_clean_subscription_payload,
    get_clean_marzban_links,
)
from bot.webhooks.hook_wata import wata_router
from bot.webhooks.hook_yoomoney import yoomoney_router
from bot.webhooks.metrics import metrics_endpoint, prometheus_middleware
from bot.portal.routes import router as portal_router

log = logging.getLogger(__name__)

# Paths that must not open a DB session (liveness probes, metrics scrape)
_NO_SESSION_PATHS = frozenset({"/health", "/healthz", "/metrics"})
_SUBSCRIPTION_PROFILE_TITLE = "☀️ KYNVPN ✅ Active"


def _subscription_profile_headers(
    *,
    user_id: int,
    key_id: int,
    expire_ts: int,
    content_disposition: str,
) -> dict[str, str]:
    title = base64.b64encode(
        _SUBSCRIPTION_PROFILE_TITLE.encode("utf-8")
    ).decode("ascii")
    return {
        "Cache-Control": "no-store",
        "Content-Disposition": content_disposition,
        "profile-title": f"base64:{title}",
        "profile-update-interval": "1",
        "subscription-userinfo": (
            "upload=0; download=0; total=0; "
            f"expire={max(int(expire_ts or 0), 0)}"
        ),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    http_client = httpx.AsyncClient(timeout=10)
    app.state.http_client = http_client
    yield
    await http_client.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(portal_router)


@app.middleware("http")
async def portal_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/web/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
    return response


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
    if (request.url.path in _NO_SESSION_PATHS
            or request.url.path == "/web/"
            or request.url.path.startswith("/web/assets/")):
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


@app.get("/health", include_in_schema=False)
async def health(request: Request):
    """Readiness probe — returns 200 only when DB and NATS are reachable."""
    details = {"db": False, "nats": False}
    errors: dict[str, str] = {}

    try:
        async with request.app.state.session_maker() as session:
            await session.execute(text("SELECT 1"))
        details["db"] = True
    except Exception as exc:
        errors["db"] = type(exc).__name__

    try:
        js = request.app.state.nats_js
        await js.account_info()
        details["nats"] = True
    except Exception as exc:
        errors["nats"] = type(exc).__name__

    status_code = 200 if all(details.values()) else 503
    payload = {
        "status": "ok" if status_code == 200 else "degraded",
        "details": details,
    }
    if errors:
        payload["errors"] = errors
    return JSONResponse(payload, status_code=status_code)


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    """Prometheus metrics scrape endpoint."""
    return await metrics_endpoint(request)


@app.get("/subscriptions/{token}", include_in_schema=False)
async def clean_subscription(token: str, request: Request):
    user_id, key_id = parse_clean_subscription_token(token)
    payload = await render_clean_subscription_payload(
        session=request.state.session,
        key_id=key_id,
        user_id=user_id,
    )
    key = await get_key_id(request.state.session, key_id)
    return PlainTextResponse(
        payload,
        media_type="text/plain; charset=utf-8",
        headers=_subscription_profile_headers(
            user_id=user_id,
            key_id=key_id,
            expire_ts=getattr(key, "subscription", 0),
            content_disposition=f'inline; filename="vpnhub-sub-{user_id}-{key_id}.txt"',
        ),
    )


@app.get("/subscriptions/{token}/clash", include_in_schema=False)
async def clash_subscription(token: str, request: Request):
    user_id, key_id = parse_clean_subscription_token(token)
    links = await get_clean_marzban_links(
        session=request.state.session,
        key_id=key_id,
        user_id=user_id,
    )
    if not links:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    yaml_content = build_clash_config(links)
    if not yaml_content:
        raise HTTPException(status_code=404, detail="no_parseable_proxies")
    key = await get_key_id(request.state.session, key_id)
    return PlainTextResponse(
        yaml_content,
        media_type="text/yaml; charset=utf-8",
        headers=_subscription_profile_headers(
            user_id=user_id,
            key_id=key_id,
            expire_ts=getattr(key, "subscription", 0),
            content_disposition=f'attachment; filename="vpnhub-{user_id}.yaml"',
        ),
    )


@app.get("/subscriptions/{token}/singbox", include_in_schema=False)
async def singbox_subscription(token: str, request: Request):
    user_id, key_id = parse_clean_subscription_token(token)
    links = await get_clean_marzban_links(
        session=request.state.session,
        key_id=key_id,
        user_id=user_id,
    )
    if not links:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    json_content = build_singbox_config(links)
    if not json_content:
        raise HTTPException(status_code=404, detail="no_parseable_proxies")
    key = await get_key_id(request.state.session, key_id)
    return PlainTextResponse(
        json_content,
        media_type="application/json; charset=utf-8",
        headers=_subscription_profile_headers(
            user_id=user_id,
            key_id=key_id,
            expire_ts=getattr(key, "subscription", 0),
            content_disposition=f'attachment; filename="vpnhub-{user_id}.json"',
        ),
    )


app.include_router(wata_router)
app.include_router(yoomoney_router)
