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
)
from bot.misc.callbackData import BroadcastAction, BroadcastAudience
from bot.misc.language import get_lang
from bot.misc.util import CONFIG
from bot.services import broadcast_service

admin_broadcast_router = Router()
admin_broadcast_router.message.filter(IsAdmin())


class BroadcastStates(StatesGroup):
    waiting_audience = State()
    waiting_text = State()
    waiting_confirm = State()


SEGMENT_TITLE = {
    broadcast_service.BROADCAST_SEGMENT_ALL: "All users",
    broadcast_service.BROADCAST_SEGMENT_ACTIVE: "Active users",
    broadcast_service.BROADCAST_SEGMENT_NO_SUB: "Users without subscription",
    broadcast_service.BROADCAST_SEGMENT_EXPIRED_LEGACY: "Expired 3x-ui users",
}


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
        "Выберите аудиторию для рассылки:",
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
    users = await broadcast_service.get_broadcast_users(
        session,
        callback_data.segment,
    )
    await state.update_data(segment=callback_data.segment, users_count=len(users))
    await state.set_state(BroadcastStates.waiting_text)
    await call.message.edit_text(
        f"Сегмент: {SEGMENT_TITLE.get(callback_data.segment, callback_data.segment)}\n"
        f"Получателей: {len(users)}\n\n"
        f"Отправьте текст рассылки."
    )
    await call.answer()


@admin_broadcast_router.message(BroadcastStates.waiting_text)
async def broadcast_input_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not message.text:
        await message.answer("Отправьте текстовое сообщение для рассылки.")
        return
    data = await state.get_data()
    segment = data.get("segment", broadcast_service.BROADCAST_SEGMENT_ALL)
    users = await broadcast_service.get_broadcast_users(session, segment)
    await state.update_data(text=message.text, users_count=len(users))
    await state.set_state(BroadcastStates.waiting_confirm)
    preview = broadcast_service.format_broadcast_preview(
        segment_title=SEGMENT_TITLE.get(segment, segment),
        users_count=len(users),
        text=message.text,
    )
    await message.answer(preview, reply_markup=await broadcast_confirm_keyboard())


@admin_broadcast_router.callback_query(BroadcastAction.filter())
async def broadcast_action(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: BroadcastAction,
    state: FSMContext,
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    if callback_data.action == "cancel":
        await state.clear()
        await call.message.edit_text("Рассылка отменена.")
        await call.answer()
        return

    if callback_data.action == "edit":
        await state.set_state(BroadcastStates.waiting_text)
        await call.message.edit_text("Отправьте новый текст рассылки.")
        await call.answer()
        return

    data = await state.get_data()
    segment = data.get("segment", broadcast_service.BROADCAST_SEGMENT_ALL)
    text = data.get("text")
    if not text:
        await state.set_state(BroadcastStates.waiting_text)
        await call.message.edit_text("Текст не найден. Отправьте текст рассылки заново.")
        await call.answer()
        return

    users = await broadcast_service.get_broadcast_users(session, segment)
    await call.message.edit_text(
        f"Запуск рассылки...\nПолучателей: {len(users)}"
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
        "✅ Рассылка завершена.\n\n"
        f"Отправлено: {stats.sent}\n"
        f"Ошибок: {stats.failed}"
    )
    await call.answer()
