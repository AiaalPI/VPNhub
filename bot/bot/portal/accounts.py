"""Confirmed identity links and a shared, live read model for both channels.

Entitlements stay in their original records: no copying keys, doubling paid time
or background synchronization. Both interfaces read the same committed rows.
"""
import secrets
import time
from datetime import timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from bot.database.models.main import Groups, Keys, Payments, Persons
from bot.misc.util import CONFIG
from bot.portal.models import WebAccount, WebOrder, WebSubscription, WebTelegramChallenge, WebTelegramLink, WebTrial
from bot.portal.security import digest

LINK_PREFIX = "web_"
LINK_TTL = 600


async def linked_person(session, account_id: str, *, lock: bool = False):
    query = select(Persons).join(WebTelegramLink, WebTelegramLink.telegram_tgid == Persons.tgid).where(
        WebTelegramLink.account_id == account_id)
    if lock:
        query = query.with_for_update(of=Persons)
    person = await session.scalar(query)
    if person and person.blocked:
        raise HTTPException(403, "Аккаунт недоступен")
    return person


async def linked_account(session, telegram_id: int):
    return await session.scalar(select(WebAccount).join(WebTelegramLink).where(
        WebTelegramLink.telegram_tgid == telegram_id, WebAccount.disabled.is_(False)))


async def begin_link(session, account_id: str):
    # Serialize replacing challenges and confirmation for this email account.
    await session.scalar(select(WebAccount).where(WebAccount.id == account_id).with_for_update())
    if await session.get(WebTelegramLink, account_id):
        raise HTTPException(409, "Telegram уже привязан")
    await session.execute(delete(WebTelegramChallenge).where(WebTelegramChallenge.account_id == account_id))
    token = secrets.token_urlsafe(32)
    request_id = digest(token)
    session.add(WebTelegramChallenge(digest=request_id, account_id=account_id,
                                    expires_at=int(time.time()) + LINK_TTL))
    await session.commit()
    return token, request_id


async def claim_link(session, token: str, telegram_user):
    """Only the authenticated private /start update supplies the Telegram ID."""
    if len(token) != 43 or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in token):
        raise HTTPException(404, "Ссылка недействительна")
    row = await session.scalar(select(WebTelegramChallenge).where(
        WebTelegramChallenge.digest == digest(token)).with_for_update())
    if not row or row.expires_at <= time.time():
        raise HTTPException(404, "Ссылка истекла. Создайте новую в кабинете сайта.")
    user = await session.get(WebAccount, row.account_id)
    person = await session.scalar(select(Persons).where(Persons.tgid == telegram_user.id))
    if not user or user.disabled or (person and person.blocked):
        raise HTTPException(403, "Аккаунт недоступен")
    existing = await session.scalar(select(WebTelegramLink).where(WebTelegramLink.telegram_tgid == telegram_user.id))
    if existing or await session.get(WebTelegramLink, row.account_id):
        raise HTTPException(409, "Аккаунт уже связан. Откройте личный кабинет.")
    if row.telegram_tgid and row.telegram_tgid != telegram_user.id:
        raise HTTPException(409, "Ссылка уже открыта другим аккаунтом. Создайте новую на сайте.")
    row.telegram_tgid = telegram_user.id
    row.display_name = (telegram_user.full_name or str(telegram_user.id))[:256]
    row.username = (telegram_user.username or "")[:64]
    row.language = (telegram_user.language_code or "")[:16]
    await session.commit()
    return user.email


async def approve_link(session, token: str, telegram_id: int, *, cancel: bool = False):
    """An explicit Telegram confirmation is required, beyond opening /start.

    Otherwise an attacker could send their own website link to a victim and
    approve that victim's identity from the attacker's website session.
    """
    row = await session.scalar(select(WebTelegramChallenge).where(
        WebTelegramChallenge.digest == digest(token)).with_for_update())
    if not row or row.expires_at <= time.time() or row.telegram_tgid != telegram_id:
        raise HTTPException(409, "Ссылка недействительна")
    user = await session.get(WebAccount, row.account_id)
    person = await session.scalar(select(Persons).where(Persons.tgid == telegram_id))
    if not user or user.disabled or (person and person.blocked):
        raise HTTPException(403, "Аккаунт недоступен")
    if cancel:
        await session.delete(row)
    else:
        row.telegram_confirmed_at = int(time.time())
    await session.commit()


async def link_state(session, account_id: str):
    person = await linked_person(session, account_id)
    if person:
        return {"linked": True, "telegram_id": person.tgid, "display_name": person.fullname or str(person.tgid)}
    row = await session.scalar(select(WebTelegramChallenge).where(
        WebTelegramChallenge.account_id == account_id, WebTelegramChallenge.expires_at > int(time.time())))
    return {"linked": False, "pending": bool(row), "request_id": row.digest if row else None,
            "candidate": {"telegram_id": row.telegram_tgid, "display_name": row.display_name,
                          "confirmed": bool(row.telegram_confirmed_at)}
            if row and row.telegram_tgid else None}


async def confirm_link(session, account_id: str, request_id: str):
    user = await session.scalar(select(WebAccount).where(WebAccount.id == account_id).with_for_update())
    if not user or user.disabled:
        raise HTTPException(403, "Аккаунт недоступен")
    row = await session.scalar(select(WebTelegramChallenge).where(
        WebTelegramChallenge.account_id == account_id, WebTelegramChallenge.digest == request_id).with_for_update())
    if not row or row.expires_at <= time.time() or not row.telegram_tgid or not row.telegram_confirmed_at:
        raise HTTPException(409, "Сначала откройте ссылку в Telegram. Истёкшую ссылку нужно создать заново.")
    if await session.get(WebTelegramLink, account_id):
        raise HTTPException(409, "Telegram уже привязан")
    person = await session.scalar(select(Persons).where(Persons.tgid == row.telegram_tgid).with_for_update())
    if person and person.blocked:
        raise HTTPException(403, "Аккаунт недоступен")
    # A Telegram /start can concurrently register the same person. Use the unique
    # TG constraint, never manufacture an ID or replace an existing user.
    try:
        async with session.begin_nested():
            if person is None:
                group = await session.scalar(select(Groups.name).where(Groups.name == CONFIG.default_user_group))
                person = Persons(tgid=row.telegram_tgid, fullname=row.display_name,
                    username="@" + row.username if row.username else None,
                    lang_tg=row.language or None, banned=True, group=group)
                session.add(person)
                await session.flush()
    except IntegrityError:
        person = await session.scalar(select(Persons).where(Persons.tgid == row.telegram_tgid).with_for_update())
        if not person or person.blocked:
            raise HTTPException(409, "Не удалось связать аккаунты. Повторите попытку.") from None
    try:
        async with session.begin_nested():
            session.add(WebTelegramLink(account_id=account_id, telegram_tgid=person.tgid, created_at=int(time.time())))
            await session.flush()
    except IntegrityError:
        raise HTTPException(409, "Этот Telegram уже связан с другим email.") from None
    await session.delete(row)
    await session.commit()
    return await link_state(session, account_id)


async def telegram_access_used(session, account_id: str, *, lock: bool = False):
    person = await linked_person(session, account_id, lock=lock)
    return bool(person and (person.trial_used or await session.scalar(
        select(Keys.id).where(Keys.user_tgid == person.tgid).limit(1))))


async def web_access_used(session, telegram_id: int):
    user = await linked_account(session, telegram_id)
    if not user:
        return False
    # The same account lock as the web trial serializes cross-channel claims.
    await session.scalar(select(WebAccount).where(WebAccount.id == user.id).with_for_update())
    return bool(await session.scalar(select(WebSubscription.id).where(
        WebSubscription.account_id == user.id, WebSubscription.expires_at > 0).limit(1)))


async def snapshot(session, user):
    """Read current ownership on every request; referral_tgid is never identity."""
    person = await linked_person(session, user.id)
    keys = (await session.scalars(select(Keys).where(Keys.user_tgid == person.tgid).order_by(Keys.id))).all() if person else []
    now = int(time.time())
    subscriptions = [{"id": key.id, "expires_at": key.subscription or 0,
        "active": bool(key.subscription and key.subscription > now), "quota_gb": key.paid_quota_gb,
        "source": "telegram"} for key in keys]
    orders = (await session.scalars(select(WebOrder).where(WebOrder.account_id == user.id).order_by(WebOrder.created_at.desc()).limit(50))).all()
    history = [{"id": o.id, "months": o.months, "amount_kopecks": o.amount_kopecks,
        "created_at": o.created_at, "status": "paid" if o.paid_at else "pending", "source": "website"} for o in orders]
    if person:
        payments = (await session.scalars(select(Payments).where(Payments.user == person.id).order_by(Payments.data.desc()).limit(50))).all()
        history.extend({"id": p.id, "months": p.month_count, "amount_kopecks": int(Decimal(str(p.amount or 0)) * 100),
            "created_at": int(p.data.replace(tzinfo=timezone.utc).timestamp()) if p.data else 0,
            "status": p.status, "source": "telegram"} for p in payments)
    return {"telegram_subscriptions": subscriptions,
            "history": sorted(history, key=lambda o: o["created_at"], reverse=True)[:50]}
