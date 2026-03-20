from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.update import block_state_person
from bot.filters.main import IsAdmin
from bot.keyboards.admin_keyboard import (
    broadcast_audience_keyboard,
    broadcast_confirm_keyboard,
    broadcast_waiting_text_keyboard,
    admin_dashboard_back_keyboard,
)
from bot.misc.callbackData import BroadcastAction, BroadcastAudience
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services import broadcast_service

admin_broadcast_router = Router()
admin_broadcast_router.message.filter(IsAdmin())

_ = Localization.text


class BroadcastStates(StatesGroup):
    waiting_audience = State()
    waiting_text = State()
    waiting_confirm = State()


SEGMENT_TITLE = {
    broadcast_service.BROADCAST_SEGMENT_ALL: "all",
    broadcast_service.BROADCAST_SEGMENT_ACTIVE: "active",
    broadcast_service.BROADCAST_SEGMENT_NO_SUB: "no_sub",
    broadcast_service.BROADCAST_SEGMENT_EXPIRED_LEGACY: "expired_legacy",
}


async def _render_broadcast_entry(
    target_message: Message,
    lang: str,
) -> None:
    await target_message.edit_text(
        _("admin_broadcast_entry_text", lang),
        reply_markup=await broadcast_audience_keyboard(lang),
    )


@admin_broadcast_router.message(Command("broadcast"))
async def broadcast_start(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await state.clear()
    await state.set_state(BroadcastStates.waiting_audience)
    await message.answer(
        _("admin_broadcast_entry_text", lang),
        reply_markup=await broadcast_audience_keyboard(lang),
    )


@admin_broadcast_router.callback_query(BroadcastAudience.filter())
async def broadcast_choose_audience(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: BroadcastAudience,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    users = await broadcast_service.get_broadcast_users(
        session,
        callback_data.segment,
    )
    await state.update_data(segment=callback_data.segment, users_count=len(users))
    await state.set_state(BroadcastStates.waiting_text)
    await call.message.edit_text(
        _("admin_broadcast_waiting_text_screen", lang).format(
            segment_title=_(
                'admin_broadcast_segment_' + SEGMENT_TITLE.get(callback_data.segment, 'all'),
                lang,
            ),
            users_count=len(users),
        ),
        reply_markup=await broadcast_waiting_text_keyboard(lang),
    )
    await call.answer()


@admin_broadcast_router.message(BroadcastStates.waiting_text)
async def broadcast_input_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    if not message.text:
        await message.answer(_('admin_broadcast_text_only', lang))
        return
    data = await state.get_data()
    segment = data.get("segment", broadcast_service.BROADCAST_SEGMENT_ALL)
    users = await broadcast_service.get_broadcast_users(session, segment)
    await state.update_data(text=message.text, users_count=len(users))
    await state.set_state(BroadcastStates.waiting_confirm)
    preview = broadcast_service.format_broadcast_preview(
        segment_title=_(
            'admin_broadcast_segment_' + SEGMENT_TITLE.get(segment, 'all'),
            lang,
        ),
        users_count=len(users),
        text=message.text,
    )
    await message.answer(
        preview,
        reply_markup=await broadcast_confirm_keyboard(lang),
    )


@admin_broadcast_router.callback_query(BroadcastAction.filter())
async def broadcast_action(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: BroadcastAction,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)

    if callback_data.action == "back_admin":
        await state.clear()
        await call.message.edit_text(
            _('admin_broadcast_cancelled', lang),
            reply_markup=await admin_dashboard_back_keyboard(lang),
        )
        await call.answer()
        return

    if callback_data.action == "back_audience":
        await state.set_state(BroadcastStates.waiting_audience)
        await call.message.edit_text(
            _('admin_broadcast_entry_text', lang),
            reply_markup=await broadcast_audience_keyboard(lang),
        )
        await call.answer()
        return

    if callback_data.action == "edit":
        await state.set_state(BroadcastStates.waiting_text)
        data = await state.get_data()
        segment = data.get("segment", broadcast_service.BROADCAST_SEGMENT_ALL)
        users = await broadcast_service.get_broadcast_users(session, segment)
        await state.update_data(users_count=len(users))
        await call.message.edit_text(
            _('admin_broadcast_waiting_text_screen', lang).format(
                segment_title=_(
                    'admin_broadcast_segment_' + SEGMENT_TITLE.get(segment, 'all'),
                    lang,
                ),
                users_count=len(users),
            ),
            reply_markup=await broadcast_waiting_text_keyboard(lang),
        )
        await call.answer()
        return

    data = await state.get_data()
    segment = data.get("segment", broadcast_service.BROADCAST_SEGMENT_ALL)
    text = data.get("text")
    if not text:
        await state.set_state(BroadcastStates.waiting_text)
        users = await broadcast_service.get_broadcast_users(session, segment)
        await state.update_data(users_count=len(users))
        await call.message.edit_text(
            _('admin_broadcast_waiting_text_screen', lang).format(
                segment_title=_(
                    'admin_broadcast_segment_' + SEGMENT_TITLE.get(segment, 'all'),
                    lang,
                ),
                users_count=len(users),
            ),
            reply_markup=await broadcast_waiting_text_keyboard(lang),
        )
        await call.answer()
        return

    users = await broadcast_service.get_broadcast_users(session, segment)
    await call.message.edit_text(
        f"{_('admin_broadcast_running', lang)}\n"
        f"{_('admin_broadcast_recipients_label', lang)} {len(users)}"
    )
    stats = await broadcast_service.send_broadcast(
        bot=call.bot,
        users=users,
        text=text,
        delay_seconds=0.05,
    )
    for user_id in stats.blocked_user_ids or []:
        await block_state_person(session, user_id, True)
    await state.clear()
    await call.message.answer(
        f"{_('admin_broadcast_done', lang)}\n\n"
        f"{_('admin_broadcast_sent_label', lang)} {stats.sent}\n"
        f"{_('admin_broadcast_failed_label', lang)} {stats.failed}"
    )
    await call.answer()
