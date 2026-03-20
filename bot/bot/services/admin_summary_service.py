from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Metric, Payments, Persons, WithdrawalRequests
from bot.services.dashboard_service import SUCCESS_PAYMENT_STATUSES


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RevenueSummary:
    successful_payments_today: int
    revenue_today: float
    revenue_7_days: float
    revenue_30_days: float


@dataclass(slots=True)
class ReferralSummary:
    total_referrers: int
    invited_users: int
    paid_referrals: int
    pending_withdrawals: int


@dataclass(slots=True)
class GrowthSummary:
    metrics_count: int
    users_with_metric: int
    referrals_attached: int
    users_30_days: int


async def get_revenue_summary(session: AsyncSession) -> RevenueSummary:
    now = _utc_now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    start_7_days = now - timedelta(days=7)
    start_30_days = now - timedelta(days=30)

    successful_payments_today = await session.scalar(
        select(func.count(Payments.id)).where(
            Payments.data.is_not(None),
            Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
            Payments.data >= day_start,
            Payments.data < day_end,
        )
    )
    revenue_today = await session.scalar(
        select(func.coalesce(func.sum(Payments.amount), 0.0)).where(
            Payments.data.is_not(None),
            Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
            Payments.data >= day_start,
            Payments.data < day_end,
        )
    )
    revenue_7_days = await session.scalar(
        select(func.coalesce(func.sum(Payments.amount), 0.0)).where(
            Payments.data.is_not(None),
            Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
            Payments.data >= start_7_days,
        )
    )
    revenue_30_days = await session.scalar(
        select(func.coalesce(func.sum(Payments.amount), 0.0)).where(
            Payments.data.is_not(None),
            Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
            Payments.data >= start_30_days,
        )
    )
    return RevenueSummary(
        successful_payments_today=int(successful_payments_today or 0),
        revenue_today=float(revenue_today or 0.0),
        revenue_7_days=float(revenue_7_days or 0.0),
        revenue_30_days=float(revenue_30_days or 0.0),
    )


async def get_referral_summary(session: AsyncSession) -> ReferralSummary:
    total_referrers = await session.scalar(
        select(func.count(func.distinct(Persons.referral_user_tgid))).where(
            Persons.referral_user_tgid.is_not(None)
        )
    )
    invited_users = await session.scalar(
        select(func.count(Persons.id)).where(Persons.referral_user_tgid.is_not(None))
    )
    paid_referrals = await session.scalar(
        select(func.count(func.distinct(Persons.id)))
        .join(Payments, Payments.user == Persons.id)
        .where(
            Persons.referral_user_tgid.is_not(None),
            Payments.status.in_(SUCCESS_PAYMENT_STATUSES),
        )
    )
    pending_withdrawals = await session.scalar(
        select(func.count(WithdrawalRequests.id)).where(
            WithdrawalRequests.check_payment.is_(False)
        )
    )
    return ReferralSummary(
        total_referrers=int(total_referrers or 0),
        invited_users=int(invited_users or 0),
        paid_referrals=int(paid_referrals or 0),
        pending_withdrawals=int(pending_withdrawals or 0),
    )


async def get_growth_summary(session: AsyncSession) -> GrowthSummary:
    start_30_days = _utc_now() - timedelta(days=30)
    metrics_count = await session.scalar(select(func.count(Metric.id)))
    users_with_metric = await session.scalar(
        select(func.count(Persons.id)).where(Persons.metric.is_not(None))
    )
    referrals_attached = await session.scalar(
        select(func.count(Persons.id)).where(Persons.referral_user_tgid.is_not(None))
    )
    users_30_days = await session.scalar(
        select(func.count(Persons.id)).where(Persons.date_registered >= start_30_days)
    )
    return GrowthSummary(
        metrics_count=int(metrics_count or 0),
        users_with_metric=int(users_with_metric or 0),
        referrals_attached=int(referrals_attached or 0),
        users_30_days=int(users_30_days or 0),
    )
