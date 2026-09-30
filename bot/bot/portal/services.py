import asyncio
import json
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from urllib.parse import quote, urlencode, urlsplit

from fastapi import HTTPException
from sqlalchemy import select

from bot.database.main import REDIS_URL
from bot.database.models.main import Servers
from bot.misc.VPN.Xui.CompatXUI import CompatXUI
from bot.misc.VPN.Xui.Vless import build_vless_xhttp_link
from bot.misc.tariffs import get_paid_data_limit_gb
from bot.misc.util import CONFIG
from bot.portal.models import WebOrder, WebSubscription
from bot.portal.security import digest

log = logging.getLogger(__name__)


def plans():
    return [{"months": months, "amount_kopecks": int(price) * 100,
             "quota_gb": get_paid_data_limit_gb(months)}
            for months, price in zip((1, 3, 6, 12), CONFIG.month_cost) if int(price) > 0]


async def rate_limit(key: str, maximum: int, seconds: int):
    from redis.asyncio import Redis
    # Atomic counter and TTL: no unlimited keys after an interrupted request.
    async with Redis.from_url(REDIS_URL) as redis:
        count = await redis.eval(
            "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1, "portal:rate:" + digest(key), seconds,
        )
    if count > maximum:
        raise HTTPException(429, "Слишком много попыток. Попробуйте позже.", headers={"Retry-After": str(seconds)})


async def send_code(config, email: str, code: str):
    def send():
        message = EmailMessage()
        message["From"] = config.mail_from
        message["To"] = email
        message["Subject"] = "Код входа в KYN VPN"
        message.set_content(f"Ваш код входа: {code}\n\nОн действует 10 минут. Никому не сообщайте код.\nЕсли вы не запрашивали вход, просто проигнорируйте письмо.")
        context = ssl.create_default_context()
        if config.smtp_port == 465:
            smtp = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15, context=context)
        else:
            smtp = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            smtp.starttls(context=context)
        with smtp:
            smtp.login(config.smtp_user, config.smtp_password)
            smtp.send_message(message)
    await asyncio.to_thread(send)


def checkout_url(order, config):
    return "https://yoomoney.ru/quickpay/confirm.xml?" + urlencode({
        "receiver": CONFIG.yoomoney_wallet_token, "quickpay-form": "shop",
        "targets": f"KYN VPN — {order.months} мес.", "paymentType": "SB",
        "sum": f"{order.amount_kopecks / 100:.2f}", "label": "kw1_" + order.id,
        "successURL": config.origin + "/web/#account",
    })


async def apply_payment(session, order_id: str, operation_id: str, amount: int):
    """Only called after verifying the provider signature, never on redirect."""
    order = await session.scalar(select(WebOrder).where(WebOrder.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(404, "Заказ не найден")
    if order.amount_kopecks != amount or not operation_id or len(operation_id) > 128:
        raise HTTPException(400, "Параметры платежа не совпадают с заказом")
    if order.paid_at:
        if order.operation_id != operation_id:
            raise HTTPException(409, "Заказ уже оплачен другой операцией")
        return order
    existing = await session.scalar(select(WebOrder.id).where(WebOrder.operation_id == operation_id))
    if existing:
        raise HTTPException(409, "Операция уже учтена")
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.id == order.subscription_id).with_for_update())
    now = int(time.time())
    sub.expires_at = max(sub.expires_at, now) + order.months * int(CONFIG.COUNT_SECOND_MOTH)
    # Add purchased allowance, preserving used traffic and avoiding a reset race.
    sub.quota_bytes += order.quota_bytes
    order.target_expiry = sub.expires_at
    order.paid_at = now
    order.operation_id = operation_id
    await session.commit()
    return order


def _client_link(sub, server, inbound):
    stream = inbound["streamSettings"]
    if isinstance(stream, str):
        stream = json.loads(stream)
    address = urlsplit(("https://" if server.connection_method else "http://") + server.ip).hostname
    if stream.get("network") == "xhttp":
        return build_vless_xhttp_link(client_id=sub.client_uuid, address=address, inbound=inbound, remark="KYN VPN | MTS XHTTP")
    if stream.get("network") not in {"tcp", "raw"} or stream.get("security") != "reality":
        raise ValueError("Unsupported portal inbound")
    reality = stream["realitySettings"]
    client = reality.get("settings", {})
    params = {"type": "tcp", "security": "reality", "encryption": "none",
              "flow": "xtls-rprx-vision", "sni": client.get("serverName") or reality["serverNames"][0],
              "fp": client.get("fingerprint") or "chrome", "pbk": client.get("publicKey") or client.get("password"),
              "sid": reality["shortIds"][0], "spx": "/"}
    if not all(params.values()) or not address:
        raise ValueError("Incomplete REALITY settings")
    host = f"[{address}]" if ":" in address else address
    return f"vless://{sub.client_uuid}@{host}:{inbound['port']}?{urlencode(params)}#KYN%20VPN"


async def panel_access(session, sub, provision=False):
    """Persisted identities + absolute expiry make an interrupted create retryable."""
    server = await session.get(Servers, sub.server_id)
    if not server or not server.work or int(server.type_vpn) != CONFIG.TypeVpn.VLESS.value:
        raise ValueError("Portal server unavailable")
    client = CompatXUI(full_address=("https://" if server.connection_method else "http://") + server.ip,
                       panel="sanaei", https=server.connection_method, timeout=15)
    try:
        await client.login(username=server.login, password=server.password)
        result = await client.request(method="GET", endpoint="/panel/api/inbounds/list")
        if not result.get("success"):
            raise ValueError("Cannot read inbounds")
        ids = list(dict.fromkeys([int(server.inbound_id), *CONFIG.xui_fallback_inbound_ids]))
        inbounds = [i for i in result["obj"] if i["id"] in ids and i.get("enable")]
        if set(i["id"] for i in inbounds) != set(ids):
            raise ValueError("An inbound is unavailable")
        email = "web." + sub.id
        matches = []
        for inbound in inbounds:
            settings = inbound["settings"]
            settings = json.loads(settings) if isinstance(settings, str) else settings
            matches.extend(c for c in settings.get("clients", []) if c.get("email") == email)
        if provision:
            payload = {"id": sub.client_uuid, "email": email, "enable": True,
                       "flow": "xtls-rprx-vision", "security": "auto", "limitIp": CONFIG.limit_ip,
                       "totalGB": sub.quota_bytes, "expiryTime": sub.expires_at * 1000,
                       "subId": sub.sub_id, "reset": 0}
            if matches:
                if any(c.get("id") != sub.client_uuid for c in matches):
                    raise ValueError("Panel identity mismatch")
                result = await client.request(method="POST", endpoint="/panel/api/clients/update/" + quote(email, safe=""), json=payload)
            else:
                result = await client.request(method="POST", endpoint="/panel/api/clients/add", json={"client": payload, "inboundIds": ids})
            if not result.get("success"):
                raise ValueError("Panel rejected client")
            if matches and len(matches) != len(inbounds):
                result = await client.request(method="POST", endpoint="/panel/api/clients/" + quote(email, safe="") + "/attach", json={"inboundIds": ids})
                if not result.get("success"):
                    raise ValueError("Panel rejected inbound attachment")
            result = await client.request(method="GET", endpoint="/panel/api/inbounds/list")
            if not result.get("success"):
                raise ValueError("Cannot verify provisioned client")
            matches = []
            for inbound in result["obj"]:
                if inbound["id"] not in ids:
                    continue
                settings = inbound["settings"]
                settings = json.loads(settings) if isinstance(settings, str) else settings
                matches.extend(c for c in settings.get("clients", []) if c.get("email") == email)
            if len(matches) != len(ids) or any(c.get("id") != sub.client_uuid or not c.get("enable")
                    or int(c.get("expiryTime", 0)) != sub.expires_at * 1000 for c in matches):
                raise ValueError("Client verification failed")
            # The panel dynamically updates Xray; no service restart is required.
            sub.provisioned_until = sub.expires_at
            await session.commit()
        if len(matches) != len(inbounds) or any(c.get("id") != sub.client_uuid or not c.get("enable") for c in matches):
            raise ValueError("Client is missing or disabled")
        return [_client_link(sub, server, i) for i in sorted(inbounds, key=lambda i: i["id"])]
    finally:
        await client.close()


async def ensure_provisioned(session, sub_id):
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.id == sub_id).with_for_update())
    if sub and sub.expires_at > int(time.time()) and sub.provisioned_until < sub.expires_at:
        try:
            await panel_access(session, sub, provision=True)
        except Exception as exc:
            # Payment stays recorded. Webhook retries and the cabinet retry the
            # same identity and expiry; neither charges nor extends again.
            await session.rollback()
            log.warning("event=portal.provision_failed subscription_id=%s error_type=%s", sub_id, type(exc).__name__)
            raise HTTPException(503, "Подписка оформлена. Подключение готовится, нажмите «Повторить настройку» в кабинете.") from None
