from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Payments, Persons, Servers
from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message

_ = Localization.text

admin_errors_router = Router()
admin_errors_router.message.filter(IsAdmin())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@admin_errors_router.callback_query(F.data == "admin_dash:errors")
async def admin_errors_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    now_ts = int(_utc_now().timestamp())
    start_24h = _utc_now() - timedelta(days=1)

    # Proxy metric: users with active key but missing server assignment.
    connection_errors = await session.scalar(
        select(func.count(Keys.id))
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(
            Persons.blocked.is_(False),
            Keys.subscription > now_ts,
            Keys.server.is_(None),
        )
    )

    # Proxy metric: payment rows with problematic status for last 24h.
    subscription_errors = await session.scalar(
        select(func.count(Payments.id)).where(
            and_(
                Payments.data.is_not(None),
                Payments.data >= start_24h,
                or_(
                    Payments.status.is_(None),
                    Payments.status.in_(["pending", "failed", "error"]),
                ),
            )
        )
    )

    # Proxy metric: servers marked as unavailable.
    server_timeout_errors = await session.scalar(
        select(func.count(Servers.id)).where(
            or_(Servers.work.is_(False), Servers.auto_work.is_(False))
        )
    )

    text = _("admin_errors_stats_text", lang).format(
        connection_errors=int(connection_errors or 0),
        subscription_errors=int(subscription_errors or 0),
        server_timeout_errors=int(server_timeout_errors or 0),
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
