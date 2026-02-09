import asyncio
import logging
import re

from aiogram import Router, F, html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery
)
from aiogram.utils.formatting import Text, Code, Bold
from nats.js import JetStreamContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_static_user_bd
from bot.database.methods.get import (
    get_server,
    get_all_static_user,
    get_location_id,
    get_vds_location,
    get_vds_id, get_name_location_server, get_static_user,
)
from bot.database.methods.insert import add_static_user
from bot.database.methods.update import update_static_wg
from bot.database.models.main import StaticPersons
from bot.handlers.admin.location_control import show_list_locations
from bot.keyboards.reply.admin_reply import (
    static_user_menu
)
from bot.keyboards.inline.admin_inline import (
    delete_static_user,
    vds_list_menu,
    protocol_list_menu
)
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.callbackData import (
    DeleteStaticUser,
    ChooseLocations,
    ChooseVdsList,
    ChooseProtocolList,
)
from bot.misc.language import Localization, get_lang
from bot.misc.remove_key_servise.publisher import remove_key_server
from bot.misc.util import CONFIG
from bot.service.create_file_str import str_to_file
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

static_user = Router()

class StaticUser(StatesGroup):
    static_user_server = State()
    static_user_name = State()


@static_user.message(F.text.in_(btn_text('admin_static_add_user_btn')))
async def add_static_user_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await show_list_locations(
        session,
        message,
        state,
        lang,
        'new',
        True
    )

@static_user.callback_query(F.data == 'back_choose_locations')
async def add_static_user_handler(
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
        'edit',
        True
    )


@static_user.callback_query(ChooseLocations.filter())
async def choose_location_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ChooseLocations
):
    lang = await get_lang(session, call.from_user.id, state)
    active_location = await get_location_id(session, callback_data.id)
    vds_list = await get_vds_location(session, callback_data.id)
    await edit_message(
        call.message,
        text=_('choose_vds', lang),
        reply_markup=await vds_list_menu(
            active_location.id,
            vds_list,
            lang,
            True
        )
    )


@static_user.callback_query(ChooseVdsList.filter())
async def choose_protocol_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ChooseVdsList
):
    lang = await get_lang(session, call.from_user.id, state)
    vds = await get_vds_id(session, callback_data.vds_id)
    await edit_message(
        call.message,
        text=_('choose_protocol', lang)
        .format(vds_ip=vds.ip),
        reply_markup=await protocol_list_menu(
            vds.location, vds.id, vds.servers, lang, True
        )
    )


@static_user.callback_query(ChooseProtocolList.filter())
async def input_username_static(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ChooseProtocolList
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    protocol = await get_server(session, callback_data.protocol_id)
    await state.update_data(protocol=protocol)
    await edit_message(
        call.message,
        text=_('static_input_name_user', lang)
    )
    await state.set_state(StaticUser.static_user_name)


async def validate_email(email: str, lang) -> (bool, str):
    if len(email.encode()) > 30:
        return False, _('error_name_static_len', lang)
    if " " in email:
        return False, _('error_name_static_space', lang)
    if email != email.lower():
        return False, _('error_name_static_lower', lang)
    email_pattern = r'^[a-z0-9@._-]+$'
    if not re.match(email_pattern, email):
        return False, _('error_name_static_email', lang)
    return True, None


@static_user.message(StaticUser.static_user_name)
async def add_user_in_server(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    val_email = await validate_email(message.text.strip(), lang)
    if not val_email[0]:
        await message.answer(val_email[1])
        return
    user_data = await state.get_data()
    protocol = user_data['protocol']
    name = message.text.strip()
    try:
        user =  await add_static_user(session, name, protocol.id)
    except IntegrityError:
        log.info('error add static user UNIQUE constraint -- OK')
        await message.answer(_('error_write_bd_key_create', lang))
        return
    try:
        sever_manager = ServerManager(protocol)
        await sever_manager.login()
        if protocol.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            pub_key = await sever_manager.add_client(name, 0)
            await update_static_wg(session, user.id, pub_key)
        else:
            await sever_manager.add_client(name, 0)
    except Exception as e:
        log.error(e, 'error connecting to server')
        await message.answer(_('error_connect_serer', lang))
        return
    await message.answer(
        _('static_user_create_success', lang).format(name=name),
        reply_markup=await static_user_menu(lang)
    )
    await state.clear()


@static_user.message(
    F.text.in_(btn_text('admin_static_show_users_btn'))
)
async def show_static_user_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    try:
        all_static_user = await get_all_static_user(session=session)
        if len(all_static_user) == 0:
            await message.answer(_('none_list_static_user', lang))
            return
    except Exception as e:
        log.error(e, 'error get all static user')
        await message.answer(_('error_get_static_user', lang))
        return
    await message.answer(_('list_static_user', lang))
    for user in all_static_user:
        try:
            if user.server is None:
                await delete_static_user_bd(session, user.name)
                await message.answer(
                    _('list_static_user_none_server_delete', lang)
                )
                continue
            message_text = Text(
                _('show_user', lang), Bold(user.name), '\n',
                _('show_key', lang), _('download', lang)
            )
            message_static_user = await message.answer(
                **message_text.as_kwargs(),
                reply_markup=await delete_static_user(
                    user.name,
                    user.server_table.id,
                    lang
                )
            )
            name_location = await get_name_location_server(
                session, user.server_table.id
            )
            asyncio.create_task(
                get_key_static_user(
                    message_static_user, user, name_location, lang
                )
            )
        except Exception as e:
            log.error('error connect server', exc_info=e)
            continue


async def get_key_static_user(
    message: Message,
    user: StaticPersons,
    name_location: str,
    lang
):
    try:
        serve_manager = ServerManager(user.server_table)
        await serve_manager.login()
        if user.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            config = await serve_manager.get_key(
                name=user.wg_public_key,
                name_key=name_location,
                key_id=0
            )
        else:
            config = await serve_manager.get_key(
                name=user.name,
                name_key=name_location,
                key_id=0
            )
        if user.server_table.type_vpn == CONFIG.TypeVpn.AMNEZIA_WG.value:
            try:
                await message.delete()
            except Exception as e:
                pass
            file_name = f'{user.name}.conf'
            await message.answer_document(
                document=await str_to_file(
                    file_name=file_name,
                    text=config.get('config')
                ),
                caption=_('show_user_2', lang)
                .format(user_name=html.quote(user.name)),
                reply_markup=await delete_static_user(
                    user.name,
                    user.server_table.id,
                    lang
                )
            )
        elif user.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            try:
                await message.delete()
            except Exception as e:
                pass
            file_name = f'{user.name}.conf'
            await message.answer_document(
                document=await str_to_file(
                    file_name=file_name,
                    text=config.key
                ),
                caption=_('show_user_2', lang)
                .format(user_name=html.quote(user.name)),
                reply_markup=await delete_static_user(
                    user.name,
                    user.server_table.id,
                    lang
                )
            )
        else:
            message_text = Text(
                _('show_user', lang), Bold(user.name), '\n',
                _('show_key', lang), Code(config)
            )
            await message.edit_text(
                **message_text.as_kwargs(),
                reply_markup=await delete_static_user(
                    user.name,
                    user.server_table.id,
                    lang
                )
            )
    except Exception as e:
        log.error('Error connect server', exc_info=e)
        message_text = Text(
            _('show_user', lang), Bold(user.name), '\n',
            _('show_key', lang), _('server_not_connected', lang)
        )
        await message.edit_text(
            **message_text.as_kwargs(),
            reply_markup=await delete_static_user(
                user.name,
                user.server_table.id,
                lang
            )
        )


@static_user.callback_query(DeleteStaticUser.filter())
async def delete_static_user_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    js: JetStreamContext,
    remove_key_subject: str,
    callback_data: DeleteStaticUser,
):
    lang = await get_lang(session, call.from_user.id, state)
    try:
        protocol = await get_server(session, callback_data.protocol_id)
        user = await get_static_user(session, callback_data.name)
        await remove_key_server(
            js,
            remove_key_subject,
            callback_data.name,
            0,
            protocol.id,
            user.wg_public_key
        )
    except Exception as e:
        await call.message.answer(
            _('error_delete_static_user_in_server', lang).format(
                name=callback_data.name
            )
        )
        log.error(e, 'error delete static user')
        return
    try:
        await delete_static_user_bd(session, callback_data.name)
    except Exception as e:
        await call.message.answer(
            _('error_delete_bd_static_user', lang)
        )
        log.error(e, 'error delete BD static user')
        return
    await edit_message(
        call.message,
        text=_('delete_static_user_success', lang)
        .format(name=callback_data.name)
    )
    await call.answer()
