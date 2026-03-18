from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.users_stats_service import get_users_stats

_ = Localization.text

admin_users_router = Router()
admin_users_router.message.filter(IsAdmin())


@admin_users_router.callback_query(F.data == "admin_dash:users")
async def admin_users_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    stats = await get_users_stats(session)
    text = _("admin_users_stats_text", lang).format(
        total_users=stats.total_users,
        active_users=stats.active_users,
        users_without_subscription=stats.users_without_subscription,
        expired_users=stats.expired_users,
        new_users_today=stats.new_users_today,
        new_users_7_days=stats.new_users_7_days,
        new_users_30_days=stats.new_users_30_days,
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
