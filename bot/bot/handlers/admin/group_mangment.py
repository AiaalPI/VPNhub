import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Text, Bold, as_list, Code
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_group
from bot.database.methods.get import (
    get_all_groups,
    get_users_group,
    get_person_id,
    get_group, get_group_name, get_count_groups, get_server_id
)
from bot.database.methods.insert import add_group
from bot.database.methods.update import (
    persons_add_group,
    update_key_users_server
)
from bot.handlers.admin.user_management import list_user, list_columns_user
from bot.keyboards.inline.admin_inline import group_control
from bot.keyboards.reply.admin_reply import admin_group_menu, back_admin_menu
from bot.misc.callbackData import GroupAction
from bot.misc.language import Localization, get_lang
from bot.misc.remove_key_servise.publisher import remove_key_server
from bot.misc.util import CONFIG
from bot.service.excel_service import get_excel_file

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

group_management = Router()


class GroupUser(StatesGroup):
    users_id_input = State()


class Group(StatesGroup):
    name_input = State()


class GroupActionName(StatesGroup):
    name_input = State()


@group_management.message(F.text.in_(btn_text('admin_groups_btn')))
async def group_panel(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('admin_group_control_message', lang),
        reply_markup=await admin_group_menu(lang)
    )
    await state.clear()


@group_management.message(F.text.in_(btn_text('admin_groups_show_btn')))
async def group_panel(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    groups = await get_all_groups(session)
    if len(groups) == 0:
        await message.answer(_('groups_counts_zero', lang))
        return
    await message.answer(_('admin_group_list_groups', lang))
    text = await groups_obj_list(groups)
    await message.answer(
        **text.as_kwargs(),
        reply_markup=await group_control(lang)
    )
    await state.clear()


async def groups_obj_list(groups):
    number_group = 1
    list_text = []
    for group in groups:
        text_obj = Text(
            number_group, ') ', Code(group['group'].name), ' -- ',
            Bold(group['count_user']), ' 👨‍💼  ',
            Bold(group['count_server']), '  🖥'
        )
        list_text.append(text_obj)
        number_group += 1
    return as_list(*list_text, sep='\n')


@group_management.callback_query(GroupAction.filter())
async def show_group_user(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: GroupAction
):
    lang = await get_lang(session, callback.from_user.id, state)
    await state.update_data(action=callback_data.action)
    await callback.message.answer(_('group_input_name', lang))
    await state.set_state(GroupActionName.name_input)
    await callback.answer()


@group_management.message(GroupActionName.name_input)
async def choosing_action(
    message: Message,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    group = await get_group_name(session, message.text.strip())
    if group is None:
        text = Text(
            _('group_name_not_found', lang).format(
                name=message.text.strip()
            )
        )
        await message.answer(
            **text.as_kwargs(),
        )
        return
    data = await state.get_data()
    action = data.get('action')
    await state.update_data(group_id=group.id)
    if action == 'show':
        await action_show_group_user(message, session, group.id, lang)
    elif action == 'delete':
        await action_delete_group(
            message,
            session,
            js,
            remove_key_subject,
            group.id,
            lang
        )
    elif action == 'add' or action == 'exclude':
        await action_update_users_group(message, state, lang)
    else:
        log.error('Action not found')


async def action_show_group_user(
    message: Message,
    session: AsyncSession,
    id_group: int,
    lang: str
):
    users = await get_users_group(session, id_group)
    if len(users) == 0:
        await message.answer(
            _('admin_group_list_groups_none', lang),
            show_alert=True
        )
        return
    list_users = []
    count = 1
    for user in users:
        list_users.append(await list_user(user, count))
        count += 1
    file = await get_excel_file(
        await list_columns_user(lang),
        list_users,
        'Users Group'
    )
    try:
        await message.answer_document(
            file,
            caption=_('admin_group_list_groups_file', lang)
        )
    except Exception as e:
        await message.answer(
            _('error_list_of_all_users_file', lang)
        )
        log.error('error send file all_user.txt', exc_info=e)


async def action_update_users_group(
    message: Message,
    state: FSMContext,
    lang: str
):
    await message.answer(
        _('admin_group_user_input_id', lang),
        reply_markup=await back_admin_menu(lang)
    )
    await state.set_state(GroupUser.users_id_input)


@group_management.message(GroupUser.users_id_input)
async def add_group_users(
    message: Message,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    data = await state.get_data()
    group = await get_group(session, int(data['group_id']))
    users_id_str = message.text.strip().split(',')
    users_id_number = []
    for id_user in users_id_str:
        if id_user.isdigit():
            users_id_number.append(int(id_user))
    users = await get_person_id(session, users_id_number)
    users_id = []
    for user in users:
        await delete_users_server(session, js, remove_key_subject,  user)
        users_id.append(user.tgid)
    if data['action'] == 'add':
        count_users = await persons_add_group(session, users_id, group.name)
        message_user = _('admin_group_user_add_success', lang)
    else:
        count_users = await persons_add_group(session, users_id)
        message_user = _('admin_group_user_exclude_success', lang)
    await message.answer(
        f'{message_user} {count_users}',
        reply_markup=await admin_group_menu(lang)
    )
    await state.clear()


async def delete_users_server(
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    user
):
    for key in user.keys:
        if key.free_key:
            continue
        if key.server is not None:
            server = await get_server_id(session, key.server)
            await remove_key_server(
                js,
                remove_key_subject,
                key.user_tgid,
                key.id,
                server.id,
                key.wg_public_key
            )
    await update_key_users_server(session, user.tgid)
    return True


async def action_delete_group(
    message: Message,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    id_group: int,
    lang: str
):
    users = await get_users_group(session, id_group)
    for user in users:
        await delete_users_server(session, js, remove_key_subject,  user)
    await delete_group(session, int(id_group))
    await message.answer(
        _('admin_group_delete_success', lang)
    )


@group_management.message(F.text.in_(btn_text('admin_groups_add_btn')))
async def group_panel(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    count_group = await get_count_groups(session)
    if count_group >= CONFIG.max_count_groups:
        await message.answer(
            _('groups_max_count', lang)
            .format(count=CONFIG.max_count_groups)
        )
        return
    await message.answer(
        _('admin_group_add_input_name', lang),
        reply_markup=await back_admin_menu(lang)
    )
    await state.set_state(Group.name_input)


@group_management.message(Group.name_input)
async def add_group_users(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    group_name = message.text.strip()
    try:
        await add_group(session, group_name)
        await message.answer(
            _('admin_group_add_success', lang),
            reply_markup=await admin_group_menu(lang)
        )
    except Exception as e:
        await message.answer(
            _('admin_group_add_error', lang),
            reply_markup=await admin_group_menu(lang)
        )
        log.info('error add group', e)
    finally:
        await state.clear()
