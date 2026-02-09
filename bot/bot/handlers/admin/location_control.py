import logging

from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text, Code, Spoiler
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_location, delete_vds
from bot.database.methods.get import (
    get_all_groups,
    get_group,
    get_all_locations,
    get_location_id,
    get_vds_location,
    get_vds_id, get_vds_ip, get_all_location
)
from bot.database.methods.insert import add_location, add_vds
from bot.database.methods.update import (
    new_name_location,
    edit_work_location,
    edit_work_vds, new_name_vds,
    new_ip_vds,
    new_password_vds,
    new_limit_vds,
    location_switch_update
)
from bot.database.models.main import Location, Vds
from bot.handlers.admin.group_mangment import groups_obj_list
from bot.keyboards.inline.admin_inline import (
    location_menu,
    locations_list,
    vds_list_menu,
    vds_menu, protocol_list_menu
)
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.callbackData import (
    EditLocations,
    Locations,
    AddVds,
    VdsList,
    EditVds, ServerSwitchPay
)
from bot.misc.language import Localization, get_lang
from bot.service.edit_message import edit_message
from bot.service.excel_service import get_excel_file

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

location_control = Router()


class LocationState(StatesGroup):
    input_id = State()
    input_name = State()
    input_group = State()
    input_new_name = State()


class VdsState(StatesGroup):
    input_name = State()
    input_ip = State()
    input_vds_password = State()
    input_max_space = State()


@location_control.message(F.text.in_(btn_text('admin_locations_btn')))
async def location_btn(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await show_list_locations(session, message, state, lang, type_action='new')


@location_control.callback_query(F.data == 'back_location_list')
async def location_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await show_list_locations(
        session,
        call.message,
        state,
        lang,
        type_action='edit'
    )


async def show_list_locations(
    session: AsyncSession,
    message: Message,
    state: FSMContext,
    lang,
    type_action,
    static_user_action=False
):
    await state.clear()
    all_locations = await get_all_locations(session)
    if len(all_locations) != 0:
        if static_user_action:
            text = _('choose_location', lang)
        else:
            text = _('admin_locations_list', lang)
    else:
        text = _('locations_list_not_found', lang)
        if static_user_action:
            await message.answer(text)
            return
    if type_action == 'new':
        await message.answer(
            text,
            reply_markup=await locations_list(
                all_locations,
                lang,
                static_user_action
            )
        )
    else:
        await edit_message(
            message,
            text=text,
            reply_markup=await locations_list(
                all_locations,
                lang,
                static_user_action
            )
        )


@location_control.callback_query(Locations.filter())
async def location_control_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: Locations
):
    lang = await get_lang(session, call.from_user.id, state)
    location = await get_location_id(session, callback_data.id)
    await edit_message(
        call.message,
        text=_('select_menu_item', lang),
        reply_markup=await location_menu(
            lang, callback_data.id, location.pay_switch
        )
    )


@location_control.callback_query(F.data == 'add_location')
async def location_control_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    await call.message.answer(_('location_input_name_text', lang))
    await state.set_state(LocationState.input_name)
    await call.answer()


@location_control.message(LocationState.input_name)
async def input_name(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(name=message.text.strip())
    groups = await get_all_groups(session)
    if len(groups) == 0:
        await state.update_data(group=None)
        await create_new_location(session, lang, message, state)
        return
    groups_obj = await groups_obj_list(groups)
    text = Text(
        _('input_number_group_s', lang),
        groups_obj
    )
    await message.answer(**text.as_kwargs())
    await state.set_state(LocationState.input_group)


@location_control.message(LocationState.input_group)
async def input_group(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    group_id = message.text.strip()
    if group_id.isdigit():
        group_id = int(group_id)
    else:
        await message.answer(
            _('server_input_number_group_error', lang)
        )
        return
    if group_id == 0:
        await state.update_data(group=None)
    else:
        group = await get_group(session, group_id)
        if group is None:
            await message.answer(
                _('error_input_number_group_s', lang)
                .format(group_id=group_id)
            )
            return
        await state.update_data(group=group.name)
    await create_new_location(session, lang, message, state)


async def create_new_location(session: AsyncSession, lang, message, state):
    user_data = await state.get_data()
    del user_data['lang']
    try:
        location = Location.create_location(user_data)
        await add_location(session, location)
        await message.answer(_('location_create_text', lang))
    except Exception as e:
        log.error(f'Error creating location: {e}')
    finally:
        await state.clear()
        await show_list_locations(
            session,
            message,
            state,
            lang,
            type_action='new'
        )


@location_control.callback_query(EditLocations.filter())
async def location_control_query(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: EditLocations,
):
    lang = await get_lang(session, call.from_user.id, state)
    location = await get_location_id(session, callback_data.id)
    await state.update_data(location=location)

    if callback_data.action == 'work':
        if await edit_work_location(session, location.id):
            text = (
                _('location_work_text', lang)
                .format(location_name=location.name)
            )
        else:
            text = (
                _('location_not_work_text', lang)
                .format(location_name=location.name)
            )
        await edit_message(call.message, text=text)
    elif callback_data.action == 'edit':
        await edit_message(
            call.message,
            text=_('location_input_new_name_text', lang)
            .format(location_name=location.name)
        )
        await state.set_state(LocationState.input_new_name)
        return
    elif callback_data.action == 'del':
        try:
            await delete_location(session, location.id)
            await edit_message(
                call.message,
                text=_('location_delete_text', lang)
                .format(location_name=location.name)
            )
        except Exception as e:
            log.info('Error deleting location:', e)
            await edit_message(
                call.message,
                text=_('location_not_delete_text', lang)
            )
    elif callback_data.action == 'control_vds':
        vds_list = await get_vds_location(session, location.id)
        await edit_message(
            call.message,
            text=_('vds_list_text', lang)
            .format(location_name=location.name),
            reply_markup=await vds_list_menu(location.id, vds_list, lang)
        )
        return
    else:
        await call.message.answer(_('error_not_found', lang))
    await show_list_locations(
        session, call.message, state, lang, type_action='new'
    )


@location_control.message(LocationState.input_new_name)
async def input_group(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    name = message.text.strip()
    data = await state.get_data()
    await new_name_location(session, data['location'].id, name)
    await message.answer(_('location_new_name_success_text', lang))
    await location_btn(message, session, state)


@location_control.callback_query(AddVds.filter())
async def input_login(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: AddVds
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    await state.update_data(location=callback_data.location_id)
    await edit_message(
        call.message,
        text=_('vds_input_name_text', lang)
    )
    await state.set_state(VdsState.input_name)


@location_control.message(VdsState.input_name)
async def input_vds_name(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
):
    lang = await get_lang(session, message.from_user.id, state)
    data = await state.get_data()
    if data.get('vds_id'):
        await new_name_vds(session, data.get('vds_id'), message.text.strip())
        await back_list_vds(
            session,
            message,
            state,
            'vds_edit_name_success_text',
            lang
        )
        return
    await state.update_data(name=message.text.strip())
    await message.answer(_('vds_input_ip_text', lang))
    await state.set_state(VdsState.input_ip)


@location_control.message(VdsState.input_ip)
async def input_vds_name(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
):
    lang = await get_lang(session, message.from_user.id, state)
    vds = await get_vds_ip(session, message.text.strip())
    if vds is not None:
        await message.answer(_('vds_input_ip_text_duplicate', lang))
        return
    data = await state.get_data()
    if data.get('vds_id'):
        await new_ip_vds(session, data.get('vds_id'), message.text.strip())
        await back_list_vds(
            session,
            message,
            state,
            'vds_edit_ip_success_text',
            lang
        )
        return
    await state.update_data(ip=message.text.strip())
    await message.answer(_('vds_input_password_text', lang))
    await state.set_state(VdsState.input_vds_password)


@location_control.message(VdsState.input_vds_password)
async def input_vds_name(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    data = await state.get_data()
    if data.get('vds_id'):
        await new_password_vds(
            session,
            data.get('vds_id'),
            message.text.strip()
        )
        await back_list_vds(
            session,
            message,
            state,
            'vds_edit_pass_success_text',
            lang
        )
        return
    await state.update_data(vds_password=message.text.strip())
    await message.answer(_('vds_input_max_client_text', lang))
    await state.set_state(VdsState.input_max_space)


@location_control.message(VdsState.input_max_space)
async def input_vds_name(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    count = message.text.strip()
    if count.isdigit():
        count = int(count)
    else:
        await message.answer(
            _('server_input_number_group_error', lang)
        )
        return
    await state.update_data(max_space=count)
    data = await state.get_data()
    if data.get('vds_id'):
        await new_limit_vds(session, data.get('vds_id'), count)
        await back_list_vds(
            session,
            message,
            state,
            'vds_edit_limit_success_text', lang
        )
        return
    del data['lang']
    vds = Vds.create_vds(data)
    await add_vds(session, vds)
    await message.answer(_('vds_create_text', lang))
    vds_list = await get_vds_location(session, data['location'])
    location = await get_location_id(session, data['location'])
    await message.answer(
        _('vds_list_text', lang)
        .format(location_name=location.name),
        reply_markup=await vds_list_menu(location.id, vds_list, lang)
    )
    await state.clear()


@location_control.callback_query(VdsList.filter())
async def vds_control(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: VdsList
):
    lang = await get_lang(session, call.from_user.id, state)
    vds = await get_vds_id(session, callback_data.vds_id)
    actual_space = 0
    for protocol in vds.servers:
        actual_space += protocol.actual_space
    work = (
        _('server_use_s', lang)) \
        if vds.work else (
        _('server_not_use_s', lang)
    )
    text = Text(
        _('server_name_s', lang), vds.name, '\n',
        _('server_adress_s', lang), Code(vds.ip), '\n',
        _('server_password_vds_s', lang),
        Spoiler(vds.vds_password), '\n',
        _('space_server_text', lang).format(
            space=actual_space,
            max_space=vds.max_space
        ), '\n',
        work

    )
    try:
        await call.message.edit_text(
            **text.as_kwargs(),
            reply_markup=await vds_menu(
                lang, vds.id, callback_data.location_id
            )
        )
    except Exception as e:
        log.info('error edit vds list')
        await call.message.answer(
            **text.as_kwargs(),
            reply_markup=await vds_menu(
                lang,
                vds.id,
                callback_data.location_id
            )
        )


@location_control.callback_query(EditVds.filter())
async def vds_control_action(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: EditVds,
):
    lang = await get_lang(session, call.from_user.id, state)
    vds = await get_vds_id(session, callback_data.id)
    await state.update_data(vds=vds)

    if callback_data.action == 'work':
        if await edit_work_vds(session,vds.id):
            text = (
                _('vds_work_text', lang)
                .format(vds_ip=vds.ip)
            )
        else:
            text = (
                _('vds_not_work_text', lang)
                .format(vds_ip=vds.ip)
            )
        await edit_message(call.message, text=text)
    elif callback_data.action == 'edit_name':
        await vds_edit_all(
            call, state, lang,
            VdsState.input_name,
            'vds_input_name_text', vds
        )
        return
    elif callback_data.action == 'edit_ip':
        await vds_edit_all(
            call, state, lang,
            VdsState.input_ip,
            'vds_input_ip_text', vds
        )
        return
    elif callback_data.action == 'edit_pass':
        await vds_edit_all(
            call, state, lang,
            VdsState.input_vds_password,
            'vds_input_password_text', vds
        )
        return
    elif callback_data.action == 'edit_limit':
        await vds_edit_all(
            call, state, lang,
            VdsState.input_max_space,
            'vds_input_max_client_text', vds
        )
        return
    elif callback_data.action == 'del':
        try:
            await delete_vds(session, vds.id)
            await edit_message(
                call.message,
                text=_('vds_edit_del_success_text', lang)
                .format(server_ip=vds.ip)
            )
        except Exception as e:
            log.info(f'Error deleting vds: {e}')
            await edit_message(
                call.message,
                text=_('vds_edit_not_del_success_text', lang)
            )
    elif callback_data.action == 'control_protocol':
        await call.message.edit_text(
            _('protocol_list_text', lang)
            .format(vds_ip=vds.ip),
            reply_markup=await protocol_list_menu(
                vds.location, vds.id, vds.servers, lang
            )
        )
        return
    else:
        await call.message.answer(_('error_not_found', lang))
    vds_list = await get_vds_location(session, vds.location)
    location = await get_location_id(session, vds.location)
    await call.message.answer(
        _('vds_list_text', lang)
        .format(location_name=location.name),
        reply_markup=await vds_list_menu(location.id, vds_list, lang)
    )


async def vds_edit_all(call, state, lang, state_input, text, vds):
    await state.update_data(vds_id=vds.id)
    await edit_message(call.message, text=_(text, lang))
    await state.set_state(state_input)


async def back_list_vds(session, message, state, text, lang):
    await message.answer(_(text, lang))
    data = await state.get_data()
    vds = data['vds']
    vds_list = await get_vds_location(session, vds.location)
    location = await get_location_id(session, vds.location)
    await message.answer(
        _('vds_list_text', lang)
        .format(location_name=location.name),
        reply_markup=await vds_list_menu(location.id, vds_list, lang)
    )


@location_control.callback_query(ServerSwitchPay.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ServerSwitchPay
):
    lang = await get_lang(session, call.from_user.id, state)
    await location_switch_update(
        session,
        callback_data.id_location,
        callback_data.action
    )
    await edit_message(
        call.message,
        text=_('server_edit_switch_key', lang)
    )
    await call.message.answer(
        text=_('select_menu_item', lang),
        reply_markup=await location_menu(
            lang, callback_data.id_location, callback_data.action
        )
    )


@location_control.callback_query(F.data == 'locations_statistic')
async def location_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    list_locations = []
    count = 1
    all_locations = await get_all_location(session)
    sum_bot_actual_space = 0
    sum_bot_free_space = 0
    sum_bot_max_space = 0
    for location in all_locations:
        sum_actual_space_locations = 0
        sum_free_space_locations = 0
        sum_max_space_locations = 0
        for vds in location.vds:
            sum_actual_space = 0
            sum_max_space_locations += vds.max_space
            for protocol in vds.servers:
                sum_actual_space += protocol.actual_space
                list_locations.append(
                    [
                        count,
                        location.name,
                        vds.name,
                        vds.ip,
                        vds.vds_password,
                        ServerManager.VPN_TYPES.get(
                            protocol.type_vpn
                        ).NAME_VPN,
                        protocol.actual_space,
                        '',
                        '',
                    ]
                )
                count += 1
            list_locations.append(
                [
                    '',
                    location.name,
                    vds.name,
                    vds.ip,
                    vds.vds_password,
                    _('locations_statistic_result_server', lang),
                    sum_actual_space,
                    await free_space_stat(vds.max_space, sum_actual_space),
                    vds.max_space,
                ]
            )
            sum_actual_space_locations += sum_actual_space
            sum_free_space_locations += await free_space_stat(
                vds.max_space, sum_actual_space
            )
        list_locations.append(
            [
                '',
                location.name,
                '',
                '',
                '',
                _('locations_statistic_result_locations', lang),
                sum_actual_space_locations,
                sum_free_space_locations,
                sum_max_space_locations,
            ]
        )
        list_locations.append(
            [
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
                '',
            ]
        )
        sum_bot_actual_space += sum_actual_space_locations
        sum_bot_free_space += sum_free_space_locations
        sum_bot_max_space += sum_max_space_locations

    list_locations.append(
        [
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
        ]
    )
    list_locations.append(
        [
            '',
            '',
            '',
            '',
            '',
            _('locations_statistic_result_bot', lang),
            sum_bot_actual_space,
            sum_bot_free_space,
            sum_bot_max_space,
        ]
    )

    column_locations = [
        '№',
        _('locations_statistic_name_location', lang),
        _('locations_statistic_name_server', lang),
        _('locations_statistic_ip', lang),
        _('locations_statistic_password', lang),
        _('locations_statistic_protocol', lang),
        _('locations_statistic_actual_space', lang),
        _('locations_statistic_free_space', lang),
        _('locations_statistic_max_space', lang)
    ]

    if len(list_locations) == 0:
        await call.message.answer(_('none_list_of_locations_file', lang))
        return

    file = await get_excel_file(
        column_locations,
        list_locations,
        'Statistic Locations'
    )
    try:
        await call.message.answer_document(
            file,
            caption=_('list_of_locations_file', lang)
        )
    except Exception as e:
        log.error('error send file locations', exc_info=e)



async def free_space_stat(maximum, actual):
    if maximum > actual:
        return maximum - actual
    else:
        return 0