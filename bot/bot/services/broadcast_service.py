import asyncio
import logging
import time
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_all_user
from bot.database.models.main import Keys, Persons
from bot.services.migration_service import is_legacy_backend_type

log = logging.getLogger(__name__)


BROADCAST_SEGMENT_ALL = "all"
BROADCAST_SEGMENT_ACTIVE = "active"
BROADCAST_SEGMENT_NO_SUB = "no_subscription"
BROADCAST_SEGMENT_EXPIRED_LEGACY = "expired_legacy"


@dataclass(slots=True)
class BroadcastStats:
    sent: int = 0
    failed: int = 0
    blocked_user_ids: list[int] | None = None

    def __post_init__(self) -> None:
        if self.blocked_user_ids is None:
            self.blocked_user_ids = []


def _has_active_subscription(user: Persons, now_ts: int) -> bool:
    for key in user.keys:
        if int(getattr(key, "subscription", 0) or 0) > now_ts:
            return True
    return False


def _has_expired_legacy_key(user: Persons, now_ts: int) -> bool:
    for key in user.keys:
        server = getattr(key, "server_table", None)
        if server is None:
            continue
        if not is_legacy_backend_type(getattr(server, "type_vpn", None)):
            continue
        if int(getattr(key, "subscription", 0) or 0) <= now_ts:
            return True
    return False


async def get_broadcast_users(
    session: AsyncSession,
    segment: str,
) -> list[Persons]:
    now_ts = int(time.time())
    if segment == BROADCAST_SEGMENT_ALL:
        users = await get_all_user(session)
        return [
            user for user in users
            if not bool(getattr(user, "blocked", False))
        ]

    # Aggregate per-user subscription expiry from keys.
    # SQL equivalent:
    # - Active users: subscription_expire > NOW()
    # - No subscription: subscription_expire IS NULL OR subscription_expire <= NOW()
    subscription_subq = (
        select(
            Keys.user_tgid.label("user_tgid"),
            func.max(Keys.subscription).label("subscription_expire"),
        )
        .group_by(Keys.user_tgid)
        .subquery()
    )
    users_stmt = (
        select(Persons)
        .options(joinedload(Persons.keys).joinedload(Keys.server_table))
        .outerjoin(subscription_subq, Persons.tgid == subscription_subq.c.user_tgid)
        .where(Persons.blocked.is_(False))
        .order_by(Persons.id)
    )

    if segment == BROADCAST_SEGMENT_ACTIVE:
        result = await session.execute(
            users_stmt.where(subscription_subq.c.subscription_expire > now_ts)
        )
        return result.unique().scalars().all()
    if segment == BROADCAST_SEGMENT_NO_SUB:
        result = await session.execute(
            users_stmt.where(
                or_(
                    subscription_subq.c.subscription_expire.is_(None),
                    subscription_subq.c.subscription_expire <= now_ts,
                )
            )
        )
        return result.unique().scalars().all()
    if segment == BROADCAST_SEGMENT_EXPIRED_LEGACY:
        result = await session.execute(
            users_stmt.where(
                or_(
                    subscription_subq.c.subscription_expire.is_(None),
                    subscription_subq.c.subscription_expire <= now_ts,
                )
            )
        )
        users = result.unique().scalars().all()
        return [
            user
            for user in users
            if (not _has_active_subscription(user, now_ts))
            and _has_expired_legacy_key(user, now_ts)
        ]
    return []


def format_broadcast_preview(segment_title: str, users_count: int, text: str) -> str:
    return (
        f"📣 Предпросмотр рассылки\n\n"
        f"Сегмент: {segment_title}\n"
        f"Получателей: {users_count}\n\n"
        f"Текст:\n{text}"
    )


async def send_broadcast(
    bot: Bot,
    users: list[Persons],
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    delay_seconds: float = 0.05,
) -> BroadcastStats:
    stats = BroadcastStats()
    for user in users:
        try:
            await bot.send_message(user.tgid, text, reply_markup=reply_markup)
            stats.sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            stats.failed += 1
            stats.blocked_user_ids.append(int(user.tgid))
        except Exception:
            stats.failed += 1
            log.exception("event=broadcast.send status=failed user_id=%s", user.tgid)
        await asyncio.sleep(delay_seconds)
    return stats
