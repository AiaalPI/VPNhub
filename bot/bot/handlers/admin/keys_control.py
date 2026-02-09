import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery
)
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_key_id
from bot.database.methods.insert import add_key
from bot.database.methods.update import (
    new_time_key,
    update_switch_key_admin
)
from bot.misc.callbackData import EditKeysAdmin
from bot.misc.language import Localization, get_lang
from bot.misc.loop import delete_key
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

keys_control_router = Router()


class EditKeys(StatesGroup):
    input_key_id = State()
    input_key_subscribe = State()
    input_new_subscribe = State()
    input_switch_location = State()


@keys_control_router.callback_query(
    EditKeysAdmin.filter(F.action == 'new_key')
)
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: EditKeysAdmin,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.answer(_('edit_key_new_key', lang))
    await state.update_data(id_user=callback_data.id_user)
    await state.set_state(EditKeys.input_key_subscribe)
    await call.answer()


@keys_control_router.message(EditKeys.input_key_subscribe)
async def new_key_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    day = message.text.strip()
    if not day.isdigit():
        await message.answer(
            _('edit_key_input_key_id_error_number', lang)
        )
        return
    day = int(day)
    if day <= 0 or day > 500:
        await message.answer(_('edit_key_new_key_error_limit', lang))
        return
    data = await state.get_data()
    await add_key(
        session,
        data.get('id_user'),
        day * CONFIG.COUNT_SECOND_DAY
    )
    await message.answer(
        _('edit_key_new_key_success', lang)
    )
    try:
        lang_user = await get_lang(session, data.get('id_user'))
        await message.bot.send_message(
            data.get('id_user'),
            _('edit_key_new_key_success_message', lang_user)
        )
    except Exception as e:
        await message.answer(_('edit_key_new_key_success_error', lang))
        log.info(f'user blocked bot: {e}')
    await state.clear()


@keys_control_router.callback_query(EditKeysAdmin.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: EditKeysAdmin,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.update_data(
        action=callback_data.action,
        id_user=callback_data.id_user
    )
    await call.message.answer(_('edit_key_input_key_id', lang))
    await state.set_state(EditKeys.input_key_id)
    await call.answer()


@keys_control_router.message(EditKeys.input_key_id)
async def edit_key_actions(
    message: Message,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    key_id = message.text.strip()
    if not key_id.isdigit():
        await message.answer(
            _('edit_key_input_key_id_error_number', lang)
        )
        return
    key_id = int(key_id)
    key = await get_key_id(session, key_id)
    if key is None:
        await message.answer(
            _('edit_key_input_key_id_error_not_found', lang)
        )
        return
    data = await state.get_data()
    action = data['action']
    if action == 'delete_key':
        try:
            await delete_key(session, js, remove_key_subject, key)
        except Exception as e:
            log.error(e)
            await message.answer(
                _('edit_key_delete_admin_message_error_connect', lang)
            )
            return
        await message.answer(_('edit_key_delete_admin_message', lang))
        lang_user = await get_lang(session, key.user_tgid)
        await message.bot.send_message(
            key.user_tgid,
            _('edit_key_delete_user_message', lang_user)
        )
    elif action == 'edit_time':
        await state.set_state(EditKeys.input_new_subscribe)
        await state.update_data(key_id=key_id)
        await message.answer(_('edit_key_input_new_time', lang))
        return
    elif action == 'swith_update':
        await state.set_state(EditKeys.input_switch_location)
        await state.update_data(key_id=key_id)
        await message.answer(_('edit_key_input_switch', lang))
        return
    else:
        raise NotImplemented(f'not found action {action}')
    await state.clear()


@keys_control_router.message(EditKeys.input_new_subscribe)
async def new_key_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    day = message.text.strip()
    if not day.isdigit():
        await message.answer(_('edit_key_input_key_id_error_number', lang))
        return
    day = int(day)
    if day <= 0 or day > 500:
        await message.answer(_('edit_key_new_key_error_limit', lang))
        return
    data = await state.get_data()
    key_id = data.get('key_id')
    await new_time_key(
        session,
        key_id,
        day * CONFIG.COUNT_SECOND_DAY
    )
    await message.answer(_('edit_key_new_time_success_admin', lang))
    try:
        lang_user = await get_lang(session, data.get('id_user'))
        await message.bot.send_message(
            data.get('id_user'),
            _('edit_key_new_time_success_user', lang_user)
        )
    except Exception as e:
        await message.answer(_('edit_key_new_key_success_error', lang))
        log.info('user blocked bot')
    await state.clear()


@keys_control_router.message(EditKeys.input_switch_location)
async def new_key_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    count = message.text.strip()
    if not count.isdigit():
        await message.answer(_('edit_key_input_key_id_error_number', lang))
        return
    count = int(count)
    if count > 10000:
        await message.answer(_('edit_key_input_switch_error_limit', lang))
        return
    data = await state.get_data()
    key_id = data.get('key_id')
    await update_switch_key_admin(session, key_id, count)

    await message.answer(_('edit_key_input_switch_success_admin', lang))
    try:
        lang_user = await get_lang(session, data.get('id_user'))
        await message.bot.send_message(
            data.get('id_user'),
            _('edit_key_input_switch_success_user', lang_user)
        )
    except Exception as e:
        await message.answer(_('edit_key_new_key_success_error', lang))
        log.info('user blocked bot')
    await state.clear()