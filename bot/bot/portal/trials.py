"""A trial is committed once, before the retryable VPN panel operation."""
import secrets
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from bot.database.models.main import Servers
from bot.misc.tariffs import get_trial_data_limit_gb
from bot.misc.util import CONFIG
from bot.portal import services
from bot.portal.models import WebAccount, WebOrder, WebSubscription, WebTrial
from bot.portal.security import trial_email_digest


def offer(config):
    seconds = max(0, int(CONFIG.trial_period))
    return {"available": bool(config.enabled and config.mail_ready and config.privacy_url and config.terms_url and seconds),
            "seconds": seconds, "quota_gb": get_trial_data_limit_gb()}


async def status(session, user, config, sub):
    trial = await session.get(WebTrial, user.id)
    used = trial is not None or bool(await session.scalar(select(WebTrial.account_id).where(
        WebTrial.email_digest == trial_email_digest(config.secret, user.email))))
    plan = offer(config)
    paid = bool(await session.scalar(select(WebOrder.id).where(
        WebOrder.account_id == user.id, WebOrder.paid_at.is_not(None)).limit(1)))
    return {**plan, "eligible": bool(plan["available"] and not used and not paid and not (sub and sub.expires_at)),
            "used": used, "is_trial": bool(trial and not paid)}


async def activate(session, user, config, ip):
    if not offer(config)["available"]:
        raise HTTPException(503, "Пробный доступ временно недоступен")
    # Shared with order creation; paid fulfillment also locks the subscription.
    await session.scalar(select(WebAccount).where(WebAccount.id == user.id).with_for_update())
    trial = await session.get(WebTrial, user.id)
    if trial:
        if trial.expires_at <= int(time.time()):
            raise HTTPException(409, "Пробный период уже использован. Выберите тариф для продолжения.")
        sub_id = trial.subscription_id
        await session.commit()
    else:
        key = trial_email_digest(config.secret, user.email)
        if await session.scalar(select(WebTrial.account_id).where(WebTrial.email_digest == key)):
            raise HTTPException(409, "Для этого адреса пробный период уже использован")
        sub = await session.scalar(select(WebSubscription).where(
            WebSubscription.account_id == user.id).with_for_update().execution_options(populate_existing=True))
        paid = await session.scalar(select(WebOrder.id).where(
            WebOrder.account_id == user.id, WebOrder.paid_at.is_not(None)).limit(1))
        if paid or (sub and (sub.expires_at or sub.quota_bytes)):
            raise HTTPException(409, "Подписка уже оформлена. Пробный доступ предназначен для новых клиентов.")
        server = await session.get(Servers, sub.server_id if sub else config.server_id)
        if not server or not server.work or not server.auto_work or int(server.type_vpn) != CONFIG.TypeVpn.VLESS.value:
            raise HTTPException(503, "Подключения временно недоступны. Попробуйте позже.")
        # Only fresh claims consume this budget; shared NATs can activate up to 5/day.
        await services.rate_limit("trial-ip:" + ip, 5, 86400)
        now = int(time.time())
        try:
            if not sub:
                sub = WebSubscription(id=str(uuid.uuid4()), account_id=user.id, server_id=server.id,
                    client_uuid=str(uuid.uuid4()), sub_id=secrets.token_hex(16),
                    expires_at=0, quota_bytes=0, provisioned_until=0)
                session.add(sub)
                await session.flush()
            sub.expires_at = now + int(CONFIG.trial_period)
            sub.quota_bytes = get_trial_data_limit_gb() * 1073741824
            session.add(WebTrial(account_id=user.id, email_digest=key, subscription_id=sub.id,
                started_at=now, expires_at=sub.expires_at, quota_bytes=sub.quota_bytes))
            sub_id = sub.id
            await session.commit()
        except IntegrityError:
            # Concurrent Gmail-alias claims have different account locks but one key.
            await session.rollback()
            raise HTTPException(409, "Пробный период уже активирован для этого адреса") from None
    await services.ensure_provisioned(session, sub_id)
    return await session.get(WebSubscription, sub_id, populate_existing=True)
