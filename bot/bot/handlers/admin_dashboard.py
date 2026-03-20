from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.dashboard_service import get_dashboard_metrics

_ = Localization.text

admin_dashboard_router = Router()
admin_dashboard_router.message.filter(IsAdmin())


def _money(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


@admin_dashboard_router.callback_query(F.data.in_({"admin_dash:dashboard", "admin_dash:home"}))
async def dashboard_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    metrics = await get_dashboard_metrics(session)
    text = _('admin_dashboard_metrics_text', lang).format(
        total_users=metrics.total_users,
        active_users=metrics.active_users,
        users_without_subscription=metrics.users_without_subscription,
        active_subscriptions=metrics.active_subscriptions,
        expiring_today=metrics.expiring_today,
        expiring_in_3_days=metrics.expiring_in_3_days,
        finland_users=metrics.finland_users,
        poland_users=metrics.poland_users,
        revenue_today=_money(metrics.revenue_today),
        revenue_7_days=_money(metrics.revenue_7_days),
        revenue_30_days=_money(metrics.revenue_30_days),
    )
    await edit_message(
        call.message,
        text=text,
        reply_markup=await admin_dashboard_keyboard(lang),
    )
    await call.answer()
