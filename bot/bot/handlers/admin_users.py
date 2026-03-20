from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.handlers.admin.user_management import (
    EditUser,
    export_all_users_report,
    export_payments_report,
    export_ref_board_report,
    export_subscribed_users_report,
)
from bot.keyboards.admin_keyboard import admin_users_keyboard
from bot.keyboards.reply.admin_reply import send_user_button
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
        reply_markup=await admin_users_keyboard(lang),
    )
    await call.answer()


@admin_users_router.callback_query(F.data == "admin_users:find")
async def admin_users_find_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await state.set_state(EditUser.show_user)
    await call.message.answer(
        _("input_telegram_id_user_m", lang),
        reply_markup=await send_user_button(lang),
    )
    await call.answer()


@admin_users_router.callback_query(F.data == "admin_users:all_export")
async def admin_users_all_export_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await export_all_users_report(call.message, session, lang)
    await call.answer()


@admin_users_router.callback_query(F.data == "admin_users:paid_export")
async def admin_users_paid_export_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await export_subscribed_users_report(call.message, session, lang)
    await call.answer()


@admin_users_router.callback_query(F.data == "admin_users:payments_export")
async def admin_users_payments_export_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await export_payments_report(call.message, session, lang)
    await call.answer()


@admin_users_router.callback_query(F.data == "admin_users:ref_export")
async def admin_users_ref_export_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await export_ref_board_report(call.message, session, lang)
    await call.answer()
