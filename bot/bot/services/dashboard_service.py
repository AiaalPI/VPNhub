from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Location, Payments, Persons, Servers, Vds

SUCCESS_PAYMENT_STATUSES = ("confirmed", "paid", "success", "succeeded")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_ts(value: datetime) -> int:
    return int(value.timestamp())


def _day_bounds_utc(base: datetime) -> tuple[datetime, datetime]:
    start = base.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _subscription_subquery():
    return (
        select(
            Keys.user_tgid.label("user_tgid"),
            func.max(Keys.subscription).label("subscription_expire"),
        )
        .group_by(Keys.user_tgid)
        .subquery()
    )


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


async def get_expiring_subscriptions(session: AsyncSession, days: int) -> int:
    now_utc = _utc_now()
    today_start, tomorrow_start = _day_bounds_utc(now_utc)

    if days <= 0:
        start = today_start
        end = tomorrow_start
    else:
        start = tomorrow_start
        end = today_start + timedelta(days=days + 1)

    subscription_subq = _subscription_subquery()
    value = await session.scalar(
        select(func.count(Persons.id))
        .outerjoin(subscription_subq, Persons.tgid == subscription_subq.c.user_tgid)
        .where(
            Persons.blocked.is_(False),
            subscription_subq.c.subscription_expire.is_not(None),
            subscription_subq.c.subscription_expire >= _to_ts(start),
            subscription_subq.c.subscription_expire < _to_ts(end),
        )
    )
    return int(value or 0)


async def get_revenue_today(session: AsyncSession) -> float:
    now_utc = _utc_now()
    start, end = _day_bounds_utc(now_utc)
    value = await session.scalar(
        select(func.coalesce(func.sum(Payments.amount), 0.0)).where(
            and_(
                Payments.data.is_not(None),
                Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
                Payments.data >= start,
                Payments.data < end,
            )
        )
    )
    return float(value or 0.0)


async def get_revenue_last_7_days(session: AsyncSession) -> float:
    start = _utc_now() - timedelta(days=7)
    value = await session.scalar(
        select(func.coalesce(func.sum(Payments.amount), 0.0)).where(
            and_(
                Payments.data.is_not(None),
                Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
                Payments.data >= start,
            )
        )
    )
    return float(value or 0.0)


async def get_revenue_last_30_days(session: AsyncSession) -> float:
    start = _utc_now() - timedelta(days=30)
    value = await session.scalar(
        select(func.coalesce(func.sum(Payments.amount), 0.0)).where(
            and_(
                Payments.data.is_not(None),
                Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
                Payments.data >= start,
            )
        )
    )
    return float(value or 0.0)


async def get_active_paid_subscriptions(session: AsyncSession) -> int:
    now_ts = _to_ts(_utc_now())
    value = await session.scalar(
        select(func.count(Keys.id)).join(Persons, Persons.tgid == Keys.user_tgid).where(
            Persons.blocked.is_(False),
            Keys.subscription > now_ts,
            Keys.free_key.is_(False),
            Keys.trial_period.is_(False),
        )
    )
    return int(value or 0)


async def get_expiring_paid_subscriptions(session: AsyncSession, days: int) -> int:
    now_utc = _utc_now()
    today_start, tomorrow_start = _day_bounds_utc(now_utc)

    if days <= 0:
        start = today_start
        end = tomorrow_start
    else:
        start = tomorrow_start
        end = today_start + timedelta(days=days + 1)

    value = await session.scalar(
        select(func.count(Keys.id)).join(Persons, Persons.tgid == Keys.user_tgid).where(
            Persons.blocked.is_(False),
            Keys.free_key.is_(False),
            Keys.trial_period.is_(False),
            Keys.subscription >= _to_ts(start),
            Keys.subscription < _to_ts(end),
        )
    )
    return int(value or 0)


async def get_server_users(session: AsyncSession, aliases: list[str]) -> int:
    now_ts = _to_ts(_utc_now())
    aliases = [a.strip().lower() for a in aliases if a.strip()]
    if not aliases:
        return 0
    location_match = or_(*[func.lower(Location.name).contains(alias) for alias in aliases])
    value = await session.scalar(
        select(func.count(func.distinct(Keys.user_tgid)))
        .join(Keys.server_table)
        .join(Servers.vds_table)
        .join(Vds.location_table)
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(
            Persons.blocked.is_(False),
            Keys.subscription > now_ts,
            location_match,
        )
    )
    return int(value or 0)


@dataclass(slots=True)
class DashboardMetrics:
    total_users: int
    active_users: int
    users_without_subscription: int
    active_subscriptions: int
    expiring_today: int
    expiring_in_3_days: int
    finland_users: int
    poland_users: int
    revenue_today: float
    revenue_7_days: float
    revenue_30_days: float


async def get_dashboard_metrics(session: AsyncSession) -> DashboardMetrics:
    total_users = await get_total_users(session)
    active_users = await get_active_users(session)
    users_without_subscription = await get_users_without_subscription(session)
    active_subscriptions = await get_active_paid_subscriptions(session)
    expiring_today = await get_expiring_paid_subscriptions(session, 0)
    expiring_in_3_days = await get_expiring_paid_subscriptions(session, 3)
    finland_users = await get_server_users(session, ["finland", "финлянд"])
    poland_users = await get_server_users(session, ["poland", "польш", "warsaw", "варшав"])
    revenue_today = await get_revenue_today(session)
    revenue_7_days = await get_revenue_last_7_days(session)
    revenue_30_days = await get_revenue_last_30_days(session)
    return DashboardMetrics(
        total_users=total_users,
        active_users=active_users,
        users_without_subscription=users_without_subscription,
        active_subscriptions=active_subscriptions,
        expiring_today=expiring_today,
        expiring_in_3_days=expiring_in_3_days,
        finland_users=finland_users,
        poland_users=poland_users,
        revenue_today=revenue_today,
        revenue_7_days=revenue_7_days,
        revenue_30_days=revenue_30_days,
    )
