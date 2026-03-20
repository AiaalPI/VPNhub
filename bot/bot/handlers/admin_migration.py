from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.migration_stats_service import get_migration_stats

_ = Localization.text

admin_migration_router = Router()
admin_migration_router.message.filter(IsAdmin())


@admin_migration_router.callback_query(F.data == "admin_dash:migration")
async def admin_migration_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    stats = await get_migration_stats(session)
    text = _("admin_migration_stats_text", lang).format(
        legacy_only_users=stats.legacy_only_users,
        marzban_only_users=stats.marzban_only_users,
        dual_stack_users=stats.dual_stack_users,
        migration_flagged_users=stats.migration_flagged_users,
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
