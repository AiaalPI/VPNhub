import hmac
import ipaddress
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from bot.database.models.main import Servers
from bot.misc.util import CONFIG
from bot.portal.config import PortalConfig
from bot.portal.models import WebAccount, WebChallenge, WebOrder, WebSession, WebSubscription
from bot.portal.security import code_digest, digest, normalize_email, paid_amount, verify_notification
from bot.portal import services

router = APIRouter(prefix="/web", include_in_schema=False)
STATIC = Path(__file__).parent / "static"
COOKIE = "__Secure-kyn_session"
SESSION_TTL = 7 * 24 * 3600


def config(request):
    cfg = getattr(request.app.state, "portal_config", None) or PortalConfig.from_env()
    if not cfg.enabled:
        raise HTTPException(404, "Сайт ещё не опубликован")
    return cfg


def same_origin(request):
    cfg = config(request)
    if request.headers.get("origin") != cfg.origin:
        raise HTTPException(403, "Запрос с другого сайта запрещён")
    return cfg


def client_ip(request):
    peer = request.client.host
    try:
        address = ipaddress.ip_address(peer)
        networks = [ipaddress.ip_network(value.strip()) for value in
                    os.getenv("PORTAL_TRUSTED_PROXY_CIDRS", "").split(",") if value.strip()]
        if any(address in network for network in networks):
            return str(ipaddress.ip_address(request.headers.get("x-real-ip", peer)))
    except ValueError:
        pass
    return peer


async def account(request):
    config(request)
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 128:
        raise HTTPException(401, "Войдите по email")
    session = request.state.session
    row = await session.scalar(select(WebSession).where(WebSession.digest == digest(token), WebSession.expires_at > int(time.time())))
    user = await session.get(WebAccount, row.account_id) if row else None
    if not user or user.disabled:
        raise HTTPException(401, "Войдите по email")
    return user


class EmailInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class CodeInput(BaseModel):
    challenge: str = Field(min_length=32, max_length=64)
    code: str = Field(pattern=r"^\d{6}$")


class OrderInput(BaseModel):
    months: int
    accepted_terms: Literal[True]


@router.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@router.get("/assets/{filename}")
async def asset(filename: str):
    if filename not in {"style.css", "app.js", "favicon.svg"}:
        raise HTTPException(404)
    return FileResponse(STATIC / filename)


@router.get("/api/config")
async def public_config(request: Request):
    cfg = config(request)
    return {"plans": services.plans(), "login_available": bool(cfg.mail_ready and cfg.privacy_url),
            "checkout_available": bool(CONFIG.yoomoney_wallet_token and cfg.notification_secret and cfg.terms_url and cfg.privacy_url),
            "support_email": cfg.support_email, "terms_url": cfg.terms_url, "privacy_url": cfg.privacy_url}


@router.post("/api/auth/code")
async def request_code(data: EmailInput, request: Request):
    cfg = same_origin(request)
    if not cfg.mail_ready or not cfg.privacy_url:
        raise HTTPException(503, "Вход пока недоступен. Попробуйте позже.")
    try:
        email = normalize_email(data.email)
    except ValueError:
        raise HTTPException(422, "Проверьте адрес электронной почты") from None
    await services.rate_limit("email:" + email, 3, 900)
    await services.rate_limit("ip:" + client_ip(request), 20, 3600)
    session = request.state.session
    now = int(time.time())
    await session.execute(delete(WebChallenge).where(WebChallenge.expires_at < now))
    await session.execute(delete(WebSession).where(WebSession.expires_at < now))
    challenge = secrets.token_urlsafe(32)
    code = f"{secrets.randbelow(1000000):06d}"
    session.add(WebChallenge(id=challenge, email=email, digest=code_digest(cfg.secret, challenge, code), expires_at=now + 600, attempts=0))
    await session.commit()
    try:
        await services.send_code(cfg, email, code)
    except Exception:
        await session.execute(delete(WebChallenge).where(WebChallenge.id == challenge))
        await session.commit()
        raise HTTPException(503, "Не удалось отправить письмо. Попробуйте позже.") from None
    return {"challenge": challenge, "expires_in": 600}


@router.post("/api/auth/verify")
async def verify_code(data: CodeInput, request: Request):
    cfg = same_origin(request)
    await services.rate_limit("verify:" + client_ip(request), 60, 900)
    session = request.state.session
    row = await session.scalar(select(WebChallenge).where(WebChallenge.id == data.challenge).with_for_update())
    if not row or row.expires_at <= time.time() or row.attempts >= 5:
        raise HTTPException(401, "Код недействителен. Запросите новый.")
    row.attempts += 1
    if not hmac.compare_digest(row.digest, code_digest(cfg.secret, row.id, data.code)):
        await session.commit()
        raise HTTPException(401, "Неверный код")
    user = await session.scalar(select(WebAccount).where(WebAccount.email == row.email))
    if not user:
        # Serialize concurrent first logins using the unique email constraint.
        try:
            async with session.begin_nested():
                user = WebAccount(id=str(uuid.uuid4()), email=row.email, created_at=int(time.time()), disabled=False)
                session.add(user)
                await session.flush()
        except IntegrityError:
            user = await session.scalar(select(WebAccount).where(WebAccount.email == row.email))
    if user.disabled:
        raise HTTPException(403, "Аккаунт недоступен")
    await session.delete(row)
    token = secrets.token_urlsafe(48)
    session.add(WebSession(digest=digest(token), account_id=user.id, expires_at=int(time.time()) + SESSION_TTL))
    await session.commit()
    response = JSONResponse({"email": user.email})
    response.set_cookie(COOKIE, token, max_age=SESSION_TTL, secure=True, httponly=True, samesite="lax", path="/web")
    return response


@router.post("/api/auth/logout")
async def logout(request: Request):
    same_origin(request)
    token = request.cookies.get(COOKIE, "")
    await request.state.session.execute(delete(WebSession).where(WebSession.digest == digest(token)))
    await request.state.session.commit()
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE, path="/web", secure=True, httponly=True, samesite="lax")
    return response


def serialize_subscription(sub):
    if not sub or not sub.expires_at:
        return None
    return {"id": sub.id, "expires_at": sub.expires_at, "active": sub.expires_at > time.time(),
            "ready": sub.provisioned_until >= sub.expires_at, "quota_gb": sub.quota_bytes // 1073741824}


@router.get("/api/account")
async def dashboard(request: Request):
    user = await account(request)
    session = request.state.session
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.account_id == user.id))
    orders = (await session.scalars(select(WebOrder).where(WebOrder.account_id == user.id).order_by(WebOrder.created_at.desc()).limit(50))).all()
    return {"email": user.email, "subscription": serialize_subscription(sub), "orders": [
        {"id": o.id, "months": o.months, "amount_kopecks": o.amount_kopecks, "created_at": o.created_at,
         "paid_at": o.paid_at, "status": "paid" if o.paid_at else "pending"} for o in orders]}


@router.post("/api/orders")
async def create_order(data: OrderInput, request: Request):
    cfg = same_origin(request)
    user = await account(request)
    await services.rate_limit("orders:" + user.id, 10, 3600)
    if not (CONFIG.yoomoney_wallet_token and cfg.notification_secret and cfg.terms_url and cfg.privacy_url):
        raise HTTPException(503, "Оплата пока недоступна")
    plan = next((p for p in services.plans() if p["months"] == data.months), None)
    if not plan:
        raise HTTPException(422, "Тариф не найден")
    session = request.state.session
    # Account lock serializes subscription creation and duplicate checkout clicks.
    await session.scalar(select(WebAccount).where(WebAccount.id == user.id).with_for_update())
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.account_id == user.id))
    if not sub:
        server = await session.get(Servers, cfg.server_id)
        if not server or not server.work or not server.auto_work or int(server.type_vpn) != CONFIG.TypeVpn.VLESS.value:
            raise HTTPException(503, "Подключения временно недоступны")
        sub = WebSubscription(id=str(uuid.uuid4()), account_id=user.id, server_id=server.id,
                              client_uuid=str(uuid.uuid4()), sub_id=secrets.token_hex(16),
                              expires_at=0, quota_bytes=0, provisioned_until=0)
        session.add(sub)
        await session.flush()
    order = await session.scalar(select(WebOrder).where(WebOrder.account_id == user.id,
        WebOrder.months == data.months, WebOrder.paid_at.is_(None), WebOrder.amount_kopecks == plan["amount_kopecks"],
        WebOrder.created_at > int(time.time()) - 900).order_by(WebOrder.created_at.desc()).limit(1))
    if not order:
        order = WebOrder(id=str(uuid.uuid4()), account_id=user.id, subscription_id=sub.id,
                         months=data.months, amount_kopecks=plan["amount_kopecks"], quota_bytes=plan["quota_gb"] * 1073741824,
                         created_at=int(time.time()))
        session.add(order)
    await session.commit()
    return {"id": order.id, "url": services.checkout_url(order, cfg)}


@router.post("/api/subscription/retry")
async def retry_provision(request: Request):
    same_origin(request)
    user = await account(request)
    await services.rate_limit("provision:" + user.id, 6, 300)
    sub = await request.state.session.scalar(select(WebSubscription).where(WebSubscription.account_id == user.id))
    if not sub or sub.expires_at <= time.time():
        raise HTTPException(404, "Активной подписки пока нет")
    await services.ensure_provisioned(request.state.session, sub.id)
    return {"ok": True}


@router.get("/api/subscription")
async def subscription(request: Request):
    user = await account(request)
    await services.rate_limit("profiles:" + user.id, 20, 300)
    sub = await request.state.session.scalar(select(WebSubscription).where(WebSubscription.account_id == user.id))
    if not sub or sub.expires_at <= time.time() or sub.provisioned_until < sub.expires_at:
        raise HTTPException(404, "Активное подключение пока не готово")
    try:
        links = await services.panel_access(request.state.session, sub)
    except Exception:
        raise HTTPException(503, "Не удалось загрузить профили. Попробуйте позже.") from None
    return {"links": links}


@router.get("/api/subscription/download")
async def download(request: Request):
    payload = await subscription(request)
    return PlainTextResponse("\n".join(payload["links"]), headers={"Content-Disposition": 'attachment; filename="kyn-vpn.txt"'})


@router.post("/api/payments/yoomoney")
async def notification(request: Request):
    cfg = config(request)
    raw = await request.body()
    if len(raw) > 16384:
        raise HTTPException(413)
    try:
        pairs = parse_qsl(raw.decode("utf-8"), keep_blank_values=True, max_num_fields=40)
    except (ValueError, UnicodeError):
        raise HTTPException(400) from None
    payload = dict(pairs)
    if len(payload) != len(pairs) or not verify_notification(payload, cfg.notification_secret):
        raise HTTPException(403)
    if not payload.get("label", "").startswith("kw1_"):
        raise HTTPException(400, "Неизвестный заказ")
    try:
        amount = paid_amount(payload)
        order_id = str(uuid.UUID(payload["label"][4:]))
    except (ValueError, KeyError):
        raise HTTPException(400) from None
    try:
        order = await services.apply_payment(request.state.session, order_id, payload.get("operation_id", ""), amount)
    except IntegrityError:
        await request.state.session.rollback()
        raise HTTPException(409) from None
    await services.ensure_provisioned(request.state.session, order.subscription_id)
    return Response(status_code=200)
