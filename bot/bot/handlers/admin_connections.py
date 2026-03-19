from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Payments, Persons, Servers
from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message

_ = Localization.text

admin_connections_router = Router()
admin_connections_router.message.filter(IsAdmin())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_bounds_utc() -> tuple[datetime, datetime]:
    now = _utc_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


@admin_connections_router.callback_query(F.data == "admin_dash:connections")
async def admin_connections_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    now_ts = int(_utc_now().timestamp())
    day_start, day_end = _today_bounds_utc()

    connections_today = await session.scalar(
        select(func.count(Payments.id)).where(
            Payments.data.is_not(None),
            Payments.data >= day_start,
            Payments.data < day_end,
        )
    )
    avg_online_users = await session.scalar(
        select(func.count(func.distinct(Keys.user_tgid)))
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(Persons.blocked.is_(False), Keys.subscription > now_ts)
    )
    peak_online_users = await session.scalar(
        select(func.coalesce(func.max(Servers.actual_space), 0))
    )

    text = _("admin_connections_stats_text", lang).format(
        connections_today=int(connections_today or 0),
        avg_online_users=int(avg_online_users or 0),
        peak_online_users=int(peak_online_users or 0),
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
