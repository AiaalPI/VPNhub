import json
import logging

from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.formatting import Text, Code, Spoiler, Bold
from nats.js import JetStreamContext
from pyxui_async import InboundClientStats
from remnawave.models import UserResponseDto
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_server
from bot.database.methods.get import (
    get_vds_id,
    get_server_id,
    get_keys_id,
    get_server, get_user_tg_ids_by_wg_keys, get_keys_tg_ids
)
from bot.database.methods.insert import add_server
from bot.database.methods.update import (
    server_space_update,
    server_work_update,
    update_delete_users_server, server_auto_work_update, new_squad_server
)
from bot.database.models.main import Servers
from bot.handlers.admin.user_management import (
    list_user,
    list_columns_user
)
from bot.keyboards.inline.admin_inline import (
    choosing_connection,
    choosing_panel,
    choosing_vpn,
    protocol_list_menu,
    server_control, type_server_menu, skip_input_caddy_token,
    internal_squad_select
)
from bot.misc.VPN.Remnawave import Remnawave
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.callbackData import (
    ChoosingConnectionMethod,
    ChoosingPanel,
    ChoosingVPN,
    AddProtocol,
    ProtocolList,
    ServerWork,
    ServerUserList,
    ServerDelete, ChoosingTypeServer, ServerAutoWork, SelectInSquad,
    EditInSquad, SelectNewInSquad
)
from bot.misc.language import Localization, get_lang
from bot.misc.remove_key_servise.publisher import remove_key_server
from bot.misc.util import CONFIG
from bot.service.edit_message import edit_message
from bot.service.excel_service import get_excel_file

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

state_admin_router = Router()


class AddServer(StatesGroup):
    input_ip = State()
    input_type_vpn = State()
    input_free_server = State()
    input_connect = State()
    input_panel = State()
    input_login = State()
    input_password = State()
    input_inbound_id = State()
    input_url_cert = State()


@state_admin_router.callback_query(AddProtocol.filter())
async def add_protocol(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: AddProtocol
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    await state.update_data(vds=callback_data.vds_id)
    if CONFIG.free_vpn:
        await edit_message(
            call.message,
            text=_('server_input_type_server_text', lang),
            reply_markup=await type_server_menu(lang)
        )
    else:
        await state.update_data(free_server=False)
        await edit_message(
            call.message,
            text=_('server_input_type_vpn_text', lang),
            reply_markup=await choosing_vpn(callback_data.vds_id, lang)
        )



@state_admin_router.callback_query(ChoosingTypeServer.filter())
async def input_ip(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ChoosingTypeServer
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.update_data(free_server=callback_data.type_server)
    data = await state.get_data()
    await edit_message(
        call.message,
        text=_('server_input_type_vpn_text', lang),
        reply_markup=await choosing_vpn(data['vds'], lang)
    )



@state_admin_router.callback_query(ChoosingVPN.filter())
async def input_type_connect(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ChoosingVPN
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.update_data(type_vpn=callback_data.type)
    if callback_data.type == 0:
        await edit_message(
            call.message,
            text=_('server_input_url_cert_text', lang),
        )
        await state.set_state(AddServer.input_url_cert)
    elif (
        callback_data.type == 1
        or callback_data.type == 2
        or callback_data.type == 3
        or callback_data.type == 5
    ):
        await edit_message(
            call.message,
            text=_('server_input_ip_text', lang)
        )
        await state.set_state(AddServer.input_ip)
    elif callback_data.type == 4:
        await edit_message(
            call.message,
            text=_('server_input_ip_adres', lang, font=False),
        )
        await state.set_state(AddServer.input_ip)
    elif callback_data.type == 6:
        await edit_message(
            call.message,
            text=_('server_input_ip_remna_text', lang)
        )
        await state.set_state(AddServer.input_ip)
    else:
        await call.message.answer(
            _('server_error_choosing_type_connect_text', lang)
        )
        await state.clear()
    await call.answer()


@state_admin_router.message(AddServer.input_url_cert)
async def input_url_cert(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(outline_link=message.text.strip())
    user_data = await state.get_data()
    await create_new_protocol(session, message, state, user_data, lang)


@state_admin_router.message(AddServer.input_ip)
async def input_ip(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(ip=message.text.strip())
    if (await state.get_data()).get('type_vpn') == 4:
        await message.answer(
            _('server_input_password_panel_text',lang)
        )
        await state.set_state(AddServer.input_password)
    elif (await state.get_data()).get('type_vpn') == 6:
        await message.answer(
            _('server_input_remna_api_token_panel_text', lang)
        )
        await state.set_state(AddServer.input_login)
    else:
        await message.answer(
            _('server_input_choosing_type_connect_text', lang),
            reply_markup=await choosing_connection()
        )
        await state.set_state(AddServer.input_connect)


@state_admin_router.callback_query(
    ChoosingConnectionMethod.filter(),
    AddServer.input_connect
)
async def callback_connect(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChoosingConnectionMethod,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.update_data(connection_method=callback_data.connection)
    await call.message.answer(
        _('server_choosing_panel_control', lang),
        reply_markup=await choosing_panel()
    )
    await call.answer()
    await state.set_state(AddServer.input_panel)


@state_admin_router.callback_query(
    ChoosingPanel.filter(),
    AddServer.input_panel
)
async def input_id_connect(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChoosingConnectionMethod,
    state: FSMContext
):
    await state.update_data(panel=callback_data.panel)
    await call.message.answer(_(
        'server_input_id_connect_text',
        await get_lang(session, call.from_user.id, state)
    ))
    await call.answer()
    await state.set_state(AddServer.input_inbound_id)


@state_admin_router.message(AddServer.input_inbound_id)
async def input_inbound_id_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    if message.text.strip().isdigit():
        await state.update_data(inbound_id=int(message.text.strip()))
    else:
        await message.answer('❌ Connection ID is not a number')
        return
    await message.answer(_(
        'server_input_login_text',
        await get_lang(session, message.from_user.id, state))
    )
    await state.set_state(AddServer.input_login)


@state_admin_router.message(AddServer.input_login)
async def input_login(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(login=message.text.strip())
    if (await state.get_data()).get('type_vpn') == 6:
        await message.answer(
            _('server_input_remna_caddy_token_panel_text', lang),
            reply_markup=await skip_input_caddy_token(lang)
        )
    else:
        await message.answer(_('server_input_password_panel_text', lang))
    await state.set_state(AddServer.input_password)


@state_admin_router.callback_query(F.data == 'skip_input_caddy_token')
async def skip_input_caddy_token_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, callback.from_user.id, state)
    await edit_message(
        callback.message,
        text=_('server_rem_add_download', lang)
    )
    user_data = await state.get_data()
    await create_new_protocol(
        session, callback.message, state, user_data, lang
    )


@state_admin_router.message(AddServer.input_password)
async def input_password(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(password=message.text.strip())
    if (
        (await state.get_data()).get('type_vpn') == 3
        or (await state.get_data()).get('type_vpn') == 4
    ):
        user_data = await state.get_data()
        link = {
            'url': user_data.get('ip'),
            'password': user_data.get('password')
        }
        await state.update_data(outline_link=json.dumps(link))
    user_data = await state.get_data()
    await create_new_protocol(session, message, state, user_data, lang)


@state_admin_router.callback_query(SelectInSquad.filter())
async def selected_in_squad(
        call: CallbackQuery,
        session: AsyncSession,
        state: FSMContext,
        callback_data: SelectInSquad
):
    try:
        await call.message.delete()
    except Exception:
        log.info('Error deleting message selected squad')
    lang = await get_lang(session, call.from_user.id, state)
    await state.update_data(remnawave_squad_id=callback_data.uuid)
    user_data = await state.get_data()
    await create_new_protocol(session, call.message, state, user_data, lang)


async def create_new_protocol(
    session,
    message,
    state,
    user_data,
    lang
):
    del user_data['lang']
    try:
        server = Servers.create_server(user_data)
        server_manager = ServerManager(server)
        await server_manager.login()
        connect = await server_manager.get_all_user()
        if connect is None:
            raise ModuleNotFoundError
        if server.type_vpn == 6 and server.remnawave_squad_id is None:
            server_manager = Remnawave(server, timeout=30)
            await server_manager.login()
            all_suad = await server_manager.get_all_internal_squads()
            if all_suad.total == 0:
                server.remnawave_squad_id = None
            elif all_suad.total == 1:
                server.remnawave_squad_id = str(
                    all_suad.internal_squads[0].uuid)
            else:
                await message.answer(
                    _('remnawave_select_internal_squad', lang),
                    reply_markup=await internal_squad_select(all_suad)
                )
                return
    except Exception as e:
        await message.answer(
            _('server_error_connect', lang)
        )
        log.error('state_server.py not connect server', exc_info=e)
        await state.clear()
        await show_list_protocol(
            session, message, state, lang, user_data['vds']
        )
        return
    await state.clear()
    try:
        await add_server(session, server)
    except Exception as e:
        await message.answer(
            _('server_error_write_db_name', lang)
        )
        log.error(e, 'state_server.py not read server database')
        await show_list_protocol(
            session, message, state, lang, user_data['vds']
        )
        return
    await message.answer(
        _('server_add_success', lang)
    )
    await show_list_protocol(session, message, state, lang, user_data['vds'])


async def show_list_protocol(
    session: AsyncSession,
    message: Message,
    state: FSMContext,
    lang,
    vds_id
):
    await state.clear()
    vds = await get_vds_id(session, vds_id)
    await message.answer(
        _('protocol_list_text', lang)
        .format(vds_ip=vds.ip),
        reply_markup=await protocol_list_menu(
            vds.location, vds.id, vds.servers, lang
        )
    )


@state_admin_router.callback_query(ProtocolList.filter())
async def protocol_control_call(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ProtocolList
):
    lang = await get_lang(session, call.from_user.id, state)
    protocol = await get_server_id(session, callback_data.protocol_id)
    space = 0
    name = protocol.remnawave_squad_id
    try:
        client_server = await get_static_client(protocol)
        space = len(client_server)
        if protocol.type_vpn == CONFIG.TypeVpn.REMNAWAVE.value:
            try:
                server_manager = Remnawave(protocol, timeout=10)
                await server_manager.login()
                all_suad = await server_manager.get_all_internal_squads()
                for suad in all_suad.internal_squads:
                    if str(suad.uuid) == protocol.remnawave_squad_id:
                        name = suad.name
            except Exception as e:
                log.error('Error get internal squad', exc_info=e)
        if not await server_space_update(session, protocol.id, space):
            raise ("Failed to update the data about "
                   "the free space on the server")
        connect = True
    except Exception as e:
        log.error('error connecting to server', exc_info=e)
        connect = False
    if connect:
        space_text = _('protocol_server_text', lang).format(
            space=space
        )
    else:
        space_text = _('server_not_connect_admin', lang)
    if protocol.work:
        work_text = _("server_use_s", lang)
    else:
        work_text = _("server_not_use_s", lang)

    if protocol.auto_work:
        auto_work_text = _("server_show_s", lang)
    else:
        auto_work_text = _("server_hidden_s", lang)

    type_server = (
        _("server_type_free", lang)) \
        if protocol.free_server else (
        _("server_type_not_free", lang)
    )
    if protocol.type_vpn == CONFIG.TypeVpn.OUTLINE.value:
        text = Text(
            '\n', _('server_type_vpn_s', lang),
            ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN, '\n',
            _('server_type_free_vds_s', lang),
            Bold(type_server), '\n',
            _('server_outline_connect_s', lang),
            Code(protocol.outline_link),
            '\n', work_text, '\n', auto_work_text, '\n', space_text
        )
    elif protocol.type_vpn == CONFIG.TypeVpn.AMNEZIA_WG.value:
        link = json.loads(protocol.outline_link)
        text = Text(
            '\n', _('server_type_vpn_s', lang),
            ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN, '\n',
            _('server_type_free_vds_s', lang), Bold(type_server), '\n',
            _('server_adress_s', lang), Code(link['url']), '\n',
            _('server_password_s', lang),
            Spoiler(link['password']), '\n',
            work_text, '\n', auto_work_text, '\n', space_text
        )
    elif protocol.type_vpn == CONFIG.TypeVpn.REMNAWAVE.value:
        text = Text(
            '\n', _('server_type_vpn_s', lang),
            ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN, '\n',
            _('server_type_free_vds_s', lang), Bold(type_server), '\n',
            _('server_adress_s', lang), Code(protocol.ip), '\n',
            _('server_internal_squad', lang), Code(name), '\n',
            _('server_token_api_s', lang), Spoiler(protocol.login), '\n',
            _('server_caddy_token_api_s', lang), Spoiler(protocol.password),
            '\n',
            work_text, '\n', auto_work_text, '\n', space_text
        )
    else:
        text = Text(
            '\n', _('server_type_vpn_s', lang),
            ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN, '\n',
            _('server_type_free_vds_s', lang),
            Bold(type_server), '\n',
            _('server_adress_s', lang), Code(protocol.ip), '\n',
            _('server_type_connect_s', lang),
            f'{"Https" if protocol.connection_method else "Http"}', '\n',
            _('server_panel_control_s', lang),
            f'{"Alireza 🕹" if protocol.panel == "alireza" else "Sanaei 🖲"}',
            '\n',
            _('server_id_connect_s', lang),
            Bold(protocol.inbound_id), '\n',
            _('server_login_s', lang), Bold(protocol.login), '\n',
            _('server_password_s', lang),
            Spoiler(protocol.password), '\n',
            work_text, '\n', auto_work_text, '\n', space_text
        )
    try:
        await call.message.edit_text(
            **text.as_kwargs(),
            reply_markup=await server_control(protocol, lang)
        )
    except Exception as e:
        log.error(e, 'error edit protocol')
        await call.message.answer(
            **text.as_kwargs(),
            reply_markup=await server_control(protocol, lang)
        )


async def get_static_client(server):
    server_manager = ServerManager(server)
    await server_manager.login()
    return await server_manager.get_all_user()


@state_admin_router.callback_query(ServerWork.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ServerWork
):
    lang = await get_lang(session, call.from_user.id, state)
    protocol = await get_server_id(session, callback_data.id_protocol)
    text_working = _('server_use_active', lang).format(
        type_protocol=ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN,
    )
    text_uncorking = _('server_not_use_active', lang).format(
        type_protocol=ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN,
    )
    text_message = text_working if callback_data.work else text_uncorking
    await server_work_update(
        session, callback_data.id_protocol, callback_data.work
    )
    await edit_message(
        call.message,
        text=text_message
    )
    await show_list_protocol(session, call.message, state, lang, protocol.vds)


@state_admin_router.callback_query(ServerAutoWork.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ServerAutoWork
):
    lang = await get_lang(session, call.from_user.id, state)
    protocol = await get_server_id(session, callback_data.id_protocol)
    text_working = _('server_show_active', lang).format(
        type_protocol=ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN,
    )
    text_uncorking = _('server_hidden_active', lang).format(
        type_protocol=ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN,
    )
    text_message = text_working if callback_data.work else text_uncorking
    await server_auto_work_update(
        session, callback_data.id_protocol, callback_data.work
    )
    await edit_message(
        call.message,
        text=text_message
    )
    await show_list_protocol(session, call.message, state, lang, protocol.vds)


@state_admin_router.callback_query(ServerUserList.filter())
async def call_list_server(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ServerUserList,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    protocol = await get_server(session, callback_data.id_protocol)
    try:
        client_stats = await get_static_client(protocol)
    except Exception as e:
        await call.message.answer(_('server_not_connect_admin', lang))
        await call.answer()
        log.error('server not connect', exc_info=e)
        return
    try:
        if protocol.type_vpn == CONFIG.TypeVpn.OUTLINE.value:
            client_id = []
            all_client = list({client.name for client in client_stats})
            for client in client_stats:
                client_sr = client.name.split('.')
                if client_sr[0].isdigit() and len(client_sr) == 3:
                    client_id.append(int(client_sr[1]))
                    try:
                        all_client.remove(client.name)
                    except Exception as e:
                        log.error(f'duplicate key {client.name}')
        elif protocol.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            all_client = list({peer.publicKey for peer in client_stats})
            client_id = await get_user_tg_ids_by_wg_keys(session, all_client)
        elif protocol.type_vpn == CONFIG.TypeVpn.AMNEZIA_WG.value:
            client_id = []
            all_client = list({client.name for client in client_stats})
            for client in client_stats:
                client_sr = client.name.split('.')
                if client_sr[0].isdigit() and len(client_sr) == 3:
                    client_id.append(int(client_sr[1]))
                    try:
                        all_client.remove(client.name)
                    except Exception as e:
                        log.error(f'duplicate key {client["email"]}')
        elif protocol.type_vpn == CONFIG.TypeVpn.REMNAWAVE.value:
            client_stats: list[UserResponseDto] = client_stats
            client_id = []
            all_client = list({client.username for client in client_stats})
            for client in client_stats:
                client_sr = client.username.split('_')
                if client_sr[0].isdigit() and len(client_sr) == 3:
                    client_id.append(int(client_sr[1]))
                    try:
                        all_client.remove(client.username)
                    except Exception as e:
                        log.error(f'duplicate key {client.email}')
        else:
            client_stats: list[InboundClientStats] = client_stats
            client_id = []
            all_client = list({client.email for client in client_stats})
            for client in client_stats:
                client_sr = client.email.split('.')
                if client_sr[0].isdigit() and len(client_sr) == 3:
                    client_id.append(int(client_sr[1]))
                    try:
                        all_client.remove(client.email)
                    except Exception as e:
                        log.error(f'duplicate key {client.email}')
        if protocol.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            bot_client = await get_keys_tg_ids(session, client_id)
            all_client = []
        else:
            bot_client = await get_keys_id(session, client_id)
        if not callback_data.action:
            await delete_users_server(
                session,
                js,
                remove_key_subject,
                protocol,
                bot_client
            )
            await edit_message(
                call.message,
                text=_('key_delete_server', lang)
                .format(
                    name=ServerManager.VPN_TYPES
                    .get(protocol.type_vpn).NAME_VPN
                ),
            )
            await show_list_protocol(
                session,
                call.message,
                state,
                lang,
                protocol.vds
            )
            return
        list_client = await get_text_client(all_client, bot_client, lang)
    except Exception as e:
        await call.message.answer(_('error_get_users_bd_text', lang))
        await call.answer()
        log.error(e, 'error get users BD')
        return
    if len(list_client) == 0:
        await call.message.answer(_('file_server_user_none', lang))
        await call.answer()
        return
    file = await get_excel_file(
        await list_columns_user(lang),
        list_client,
        'UsersServer'
    )
    try:
        await call.message.answer_document(
            file,
            caption=_('file_list_users_server', lang)
            .format(
                name=ServerManager.VPN_TYPES
                .get(protocol.type_vpn).NAME_VPN
            )
        )
    except Exception as e:
        await call.message.answer(_('error_file_list_users_server', lang))
        log.error(e, 'error file send Clients_server.txt')
    await call.answer()


async def get_text_client(all_client, bot_client, lang):
    list_users = []
    count = 1
    for key in bot_client:
        list_users.append(await list_user(key.person, count, True))
        count += 1
    for unknown_client in all_client:
        unknown_list = ['' for i in range(7)]
        unknown_list[0] = _('not_found_key', lang).format(
            unknown_client=unknown_client
        )
        list_users.append(unknown_list)
    return list_users


async def delete_users_server(
    session,
    js: JetStreamContext,
    remove_key_subject: str,
    protocol,
    keys
):
    for key in keys:
        await remove_key_server(
            js,
            remove_key_subject,
            key.user_tgid,
            key.id,
            protocol.id,
            key.wg_public_key
        )
    await update_delete_users_server(session, protocol)
    await server_space_update(session, protocol.id, 0)
    return True


@state_admin_router.callback_query(ServerDelete.filter())
async def delete_server_call(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ServerDelete,
):
    lang = await get_lang(session, call.from_user.id, state)
    protocol = await get_server(session, callback_data.id_protocol)
    try:
        await delete_server(session, callback_data.id_protocol)
    except Exception as e:
        await call.message.answer(
            _('server_error_delete', lang)
        )
        log.error(e, 'error delete server')
        return
    await edit_message(
        call.message,
        text=_('server_delete_success', lang)
    )
    await show_list_protocol(session, call.message, state, lang, protocol.vds)


@state_admin_router.callback_query(EditInSquad.filter())
async def edit_in_squad_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: EditInSquad,
):
    lang = await get_lang(session, call.from_user.id, state)
    server = await get_server(session, callback_data.id_protocol)
    server_manager = Remnawave(server, timeout=30)
    await server_manager.login()
    all_suad = await server_manager.get_all_internal_squads()
    await edit_message(
        call.message,
        text=_('remnawave_select_internal_squad', lang),
        reply_markup=await internal_squad_select(
            all_suad,
            vds_id=server.vds_table.id,
            protocol_id=server.id,
            lang=lang
        )
    )


@state_admin_router.callback_query(SelectNewInSquad.filter())
async def selected_new_in_squad_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: SelectNewInSquad,
):
    await new_squad_server(
        session, callback_data.id_protocol, callback_data.uuid
    )
    server = await get_server(session, callback_data.id_protocol)
    await protocol_control_call(
        call,
        session,
        state,
        ProtocolList(vds_id=server.vds_table.id, protocol_id=server.id)
    )
