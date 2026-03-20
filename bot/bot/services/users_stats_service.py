from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Persons


def _utc_now() -> datetime:
    # Persons.date_registered is stored as naive UTC in the current schema.
    return datetime.utcnow()


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


async def get_total_users(session: AsyncSession) -> int:
    value = await session.scalar(
        select(func.count(Persons.id)).where(Persons.blocked.is_(False))
    )
    return int(value or 0)


async def get_active_users(session: AsyncSession) -> int:
    now_ts = _to_ts(_utc_now())
    subscription_subq = _subscription_subquery()
    value = await session.scalar(
        select(func.count(Persons.id))
        .outerjoin(subscription_subq, Persons.tgid == subscription_subq.c.user_tgid)
        .where(
            Persons.blocked.is_(False),
            subscription_subq.c.subscription_expire.is_not(None),
            subscription_subq.c.subscription_expire > now_ts,
        )
    )
    return int(value or 0)


async def get_users_without_subscription(session: AsyncSession) -> int:
    now_ts = _to_ts(_utc_now())
    subscription_subq = _subscription_subquery()
    value = await session.scalar(
        select(func.count(Persons.id))
        .outerjoin(subscription_subq, Persons.tgid == subscription_subq.c.user_tgid)
        .where(
            Persons.blocked.is_(False),
            or_(
                subscription_subq.c.subscription_expire.is_(None),
                subscription_subq.c.subscription_expire <= now_ts,
            ),
        )
    )
    return int(value or 0)


async def get_expired_users(session: AsyncSession) -> int:
    now_ts = _to_ts(_utc_now())
    subscription_subq = _subscription_subquery()
    value = await session.scalar(
        select(func.count(Persons.id))
        .outerjoin(subscription_subq, Persons.tgid == subscription_subq.c.user_tgid)
        .where(
            Persons.blocked.is_(False),
            subscription_subq.c.subscription_expire.is_not(None),
            subscription_subq.c.subscription_expire <= now_ts,
        )
    )
    return int(value or 0)


async def get_new_users_today(session: AsyncSession) -> int:
    now = _utc_now()
    start = _day_start_utc(now)
    end = start + timedelta(days=1)
    value = await session.scalar(
        select(func.count(Persons.id)).where(
            and_(
                Persons.blocked.is_(False),
                Persons.date_registered >= start,
                Persons.date_registered < end,
            )
        )
    )
    return int(value or 0)


async def get_new_users_last_7_days(session: AsyncSession) -> int:
    start = _utc_now() - timedelta(days=7)
    value = await session.scalar(
        select(func.count(Persons.id)).where(
            and_(Persons.blocked.is_(False), Persons.date_registered >= start)
        )
    )
    return int(value or 0)


async def get_new_users_last_30_days(session: AsyncSession) -> int:
    start = _utc_now() - timedelta(days=30)
    value = await session.scalar(
        select(func.count(Persons.id)).where(
            and_(Persons.blocked.is_(False), Persons.date_registered >= start)
        )
    )
    return int(value or 0)


@dataclass(slots=True)
class UsersStats:
    total_users: int
    active_users: int
    users_without_subscription: int
    expired_users: int
    new_users_today: int
    new_users_7_days: int
    new_users_30_days: int


async def get_users_stats(session: AsyncSession) -> UsersStats:
    return UsersStats(
        total_users=await get_total_users(session),
        active_users=await get_active_users(session),
        users_without_subscription=await get_users_without_subscription(session),
        expired_users=await get_expired_users(session),
        new_users_today=await get_new_users_today(session),
        new_users_7_days=await get_new_users_last_7_days(session),
        new_users_30_days=await get_new_users_last_30_days(session),
    )
