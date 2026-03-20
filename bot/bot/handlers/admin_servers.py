from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.handlers.admin.location_control import show_list_locations
from bot.handlers.admin.static_user_control import (
    render_static_user_list,
    render_static_users_workspace,
)
from bot.keyboards.admin_keyboard import admin_dashboard_keyboard, admin_infra_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.server_stats_service import get_server_stats

_ = Localization.text

admin_servers_router = Router()
admin_servers_router.message.filter(IsAdmin())


async def render_admin_infra_workspace(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    lang: str,
) -> None:
    stats = await get_server_stats(session)
    text = _("admin_servers_stats_text", lang).format(
        finland_users=stats.finland_users,
        poland_users=stats.poland_users,
        total_locations=stats.total_locations,
        active_locations=stats.active_locations,
        total_vds=stats.total_vds,
        active_vds=stats.active_vds,
        total_protocols=stats.total_protocols,
        active_protocols=stats.active_protocols,
        hidden_protocols=stats.hidden_protocols,
        static_users=stats.static_users,
    )
    await edit_message(
        message,
        text=text,
        reply_markup=await admin_infra_keyboard(lang),
    )


@admin_servers_router.callback_query(F.data == "admin_dash:servers")
async def admin_servers_stats_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await render_admin_infra_workspace(call.message, session, state, lang)
    await call.answer()


@admin_servers_router.callback_query(F.data == "admin_infra:locations")
async def admin_infra_locations_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await show_list_locations(
        session,
        call.message,
        state,
        lang,
        type_action='edit',
    )
    await call.answer()


@admin_servers_router.callback_query(F.data == "admin_infra:static_add")
async def admin_infra_static_add_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await show_list_locations(
        session,
        call.message,
        state,
        lang,
        type_action='edit',
        static_user_action=True,
    )
    await call.answer()


@admin_servers_router.callback_query(F.data == "admin_infra:static_list")
async def admin_infra_static_list_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    await render_static_users_workspace(call.message, session, state, lang)
    await render_static_user_list(call.message, session, state, lang)
    await call.answer()
