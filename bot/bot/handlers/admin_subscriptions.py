from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.subscription_stats_service import get_subscription_stats

_ = Localization.text

admin_subscriptions_router = Router()
admin_subscriptions_router.message.filter(IsAdmin())


@admin_subscriptions_router.callback_query(F.data == "admin_dash:subscriptions")
async def admin_subscriptions_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    stats = await get_subscription_stats(session)
    text = _("admin_subscriptions_stats_text", lang).format(
        active_subscriptions=stats.active_subscriptions,
        expire_today=stats.expire_today,
        expire_in_3_days=stats.expire_in_3_days,
        expire_in_7_days=stats.expire_in_7_days,
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
