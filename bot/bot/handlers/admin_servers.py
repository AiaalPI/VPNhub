from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.server_stats_service import get_server_stats

_ = Localization.text

admin_servers_router = Router()
admin_servers_router.message.filter(IsAdmin())


@admin_servers_router.callback_query(F.data == "admin_dash:servers")
async def admin_servers_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    stats = await get_server_stats(session)
    text = _("admin_servers_stats_text", lang).format(
        finland_users=stats.finland_users,
        japan_users=stats.japan_users,
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
