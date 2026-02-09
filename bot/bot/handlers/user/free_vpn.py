import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_key_in_user
from bot.database.methods.get import (
    get_free_vpn_server,
    get_key_id, get_key_user,
    get_name_location_server
)
from bot.database.methods.insert import add_key
from bot.database.methods.update import (
    server_space_update,
    update_server_key,
    update_key_wg
)
from bot.filters.check_free_vpn import IsWorkFreeVPN
from bot.handlers.user.edit_or_get_key import post_key_telegram
from bot.handlers.user.keys_user import show_key
from bot.keyboards.inline.user_inline import back_menu_button

from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

free_vpn_router = Router()
free_vpn_router.callback_query.filter(IsWorkFreeVPN())


@free_vpn_router.callback_query(F.data == 'free_vpn_connect_btn')
async def free_vpn_btn(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    key_user = await get_key_user(session, call.from_user.id, True)
    download = await call.message.answer(_('download', lang))

    if key_user is not None and key_user.server_table is None:
        await delete_key_in_user(session, key_user.id)
        key_user = None

    if key_user is not None:
        await show_key(session, call, lang, key_user)
        await download.delete()
        return

    free_protocol = await get_free_vpn_server(session)
    if free_protocol is None:
        await download.delete()
        await edit_message(
            call.message,
            photo='bot/img/fon.jpg',
            caption=_('not_server_free_vpn', lang),
            reply_markup=await back_menu_button(lang)
        )
        return

    key = await add_key(
        session,
        call.from_user.id,
        subscription=0,
        free_key=True
    )
    await update_server_key(session, key.id, free_protocol.id)
    try:
        key = await get_key_id(session, key.id)
        server_manager = ServerManager(free_protocol)
        name_location = await get_name_location_server(
            session,
            free_protocol.id
        )
        await server_manager.login()
        if key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            config = await server_manager.get_key(
                key.wg_public_key,
                name_key=name_location,
                key_id=key.id
            )
            await update_key_wg(session, key.id, config.public_key)
        else:
            config = await server_manager.get_key(
                call.from_user.id,
                name_key=name_location,
                key_id=key.id
            )
        server_parameters = await server_manager.get_all_user()

        await server_space_update(
            session,
            free_protocol.id,
            len(server_parameters)
        )
        await download.delete()
        await post_key_telegram(call, key, config, lang)
    except Exception as e:
        log.error(f'server not connect\n{e}')
        await download.delete()
        await call.message.answer(_('server_not_connected', lang))
