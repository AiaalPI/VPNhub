from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Persons


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_ts(value: datetime) -> int:
    return int(value.timestamp())


def _subscription_subquery():
    return (
        select(
            Keys.user_tgid.label("user_tgid"),
            func.max(Keys.subscription).label("subscription_expire"),
        )
        .group_by(Keys.user_tgid)
        .subquery()
    )


def _day_start_utc(value: datetime) -> datetime:
    return value.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_active_subscriptions(session: AsyncSession) -> int:
    now_ts = _to_ts(_utc_now())
    value = await session.scalar(
        select(func.count(Keys.id))
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(
            Persons.blocked.is_(False),
            Keys.subscription > now_ts,
            Keys.free_key.is_(False),
            Keys.trial_period.is_(False),
        )
    )
    return int(value or 0)


async def get_expire_today(session: AsyncSession) -> int:
    now = _utc_now()
    start = _day_start_utc(now)
    end = start + timedelta(days=1)
    value = await session.scalar(
        select(func.count(Keys.id))
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(
            Persons.blocked.is_(False),
            Keys.free_key.is_(False),
            Keys.trial_period.is_(False),
            Keys.subscription >= _to_ts(start),
            Keys.subscription < _to_ts(end),
        )
    )
    return int(value or 0)


async def get_expire_in_days(session: AsyncSession, days: int) -> int:
    if days <= 0:
        return await get_expire_today(session)
    now = _utc_now()
    base = _day_start_utc(now) + timedelta(days=days)
    end = base + timedelta(days=1)
    value = await session.scalar(
        select(func.count(Keys.id))
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(
            Persons.blocked.is_(False),
            Keys.free_key.is_(False),
            Keys.trial_period.is_(False),
            Keys.subscription >= _to_ts(base),
            Keys.subscription < _to_ts(end),
        )
    )
    return int(value or 0)


@dataclass(slots=True)
class SubscriptionStats:
    active_subscriptions: int
    expire_today: int
    expire_in_3_days: int
    expire_in_7_days: int


async def get_subscription_stats(session: AsyncSession) -> SubscriptionStats:
    return SubscriptionStats(
        active_subscriptions=await get_active_subscriptions(session),
        expire_today=await get_expire_today(session),
        expire_in_3_days=await get_expire_in_days(session, 3),
        expire_in_7_days=await get_expire_in_days(session, 7),
    )
