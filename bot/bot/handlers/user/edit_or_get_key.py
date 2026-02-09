import logging

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.misc.VPN.Remnawave import Remnawave
from bot.misc.util import CONFIG

from bot.database.methods.get import (
    get_person,
    get_key_id,
    get_free_server_id,
    get_name_location_server,
    get_type_vpn,
    get_free_servers,
)
from bot.database.methods.update import (
    server_space_update,
    update_server_key,
    update_switch_key,
    update_key_wg
)
from bot.keyboards.inline.user_inline import (
    renew,
    replenishment,
    user_menu,
    choose_type_vpn,
    choose_server,
    instruction_manual, user_device_remove, back_menu_button,
)
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.language import Localization, get_lang
from bot.misc.callbackData import ChooseLocation, ShowUserDevices, \
    RemoveUserDevices
from bot.misc.remove_key_servise.publisher import remove_key_server
from bot.service.create_file_str import str_to_file
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

get_key_router = Router()


@get_key_router.callback_query(ChooseLocation.filter())
async def select_location_callback(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChooseLocation,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.payment:
        await payment_choosing_vpn(session, call, callback_data, lang)
        return
    server = await get_free_server_id(
        session,
        callback_data.id_location,
        callback_data.type_vpn
    )
    if server is None:
        person = await get_person(session, call.from_user.id)
        await call.message.answer_photo(
            photo=FSInputFile('bot/img/main_menu.jpg'),
            reply_markup=await user_menu(lang, person.tgid)
        )
        await call.answer()
        return
    key = await get_key_id(session, callback_data.key_id)
    if key is None:
        raise _('error_add_server_client', lang)
    if key.server is not None:
        if (
            key.switch_location == 0
            and server.vds_table.location_table.pay_switch
        ):
            await edit_message(
                call.message,
                photo='bot/img/fon.jpg',
                caption=_('user_key_edit_pay', lang)
                .format(price_switch=CONFIG.price_switch_location_type),
                reply_markup=await replenishment(
                    config=CONFIG,
                    price=CONFIG.price_switch_location_type,
                    lang=lang,
                    type_pay=CONFIG.type_payment.get(3),
                    key_id=key.id
                )
            )
            await call.answer()
            return
        if server.vds_table.location_table.pay_switch:
            await update_switch_key(session, key.id, False)
        try:
            await remove_key_server(
                js,
                remove_key_subject,
                key.user_tgid,
                key.id,
                key.server_table.id,
                key.wg_public_key
            )
        except Exception as e:
            log.info(e, 'error pub nats')
    try:
        await update_server_key(session, key.id, server.id, reset_wg_key=True)
        download = await call.message.answer(_('download', lang))
        key = await get_key_id(session, key.id)
        server_manager = ServerManager(key.server_table)
        name_location = await get_name_location_server(
            session,
            key.server_table.id
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
                key_id=key.id,
                subscription_timestamp=key.subscription
            )
        server_parameters = await server_manager.get_all_user()
        await server_space_update(
            session,
            server.id,
            len(server_parameters)
        )
    except Exception as e:
        await update_server_key(session, key.id)
        await server_not_found(call.message, e, lang)
        await call.answer()
        log.error('error get config')
        return
    await download.delete()
    await post_key_telegram(call, key, config, lang)


async def payment_choosing_vpn(
    session: AsyncSession,
    call: CallbackQuery,
    callback_data: ChooseLocation,
    lang
) -> None:
    user = await get_person(session, call.from_user.id)
    await edit_message(
        call.message,
        photo='bot/img/pay_subscribe.jpg',
        caption=_('choosing_month_sub', lang),
        reply_markup=await renew(
            CONFIG,
            lang,
            CONFIG.type_payment.get(0),
            'back_general_menu_btn',
            trial_flag=user.trial_period,
            id_protocol=callback_data.type_vpn,
            id_location=callback_data.id_location
        )
    )


async def server_not_found(m, e, lang):
    await m.answer(_('server_not_connected', lang))
    log.error(e)


async def post_key_telegram(call: CallbackQuery, key, config, lang) -> None:
    photo = await get_img_type_vpn(key)
    if(
        key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value
        or key.server_table.type_vpn == CONFIG.TypeVpn.AMNEZIA_WG.value
    ):
        file_name = f'{key.user_tgid}.conf'
        if key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            caption = _('how_to_connect_wg', lang).format(
                name_vpn=ServerManager.VPN_TYPES.get(
                    key.server_table.type_vpn
                ).NAME_VPN
            )
            text = config.key
        else:
            caption = _('how_to_connect', lang).format(
                name_vpn=ServerManager.VPN_TYPES.get(
                    key.server_table.type_vpn)
                .NAME_VPN,
                config=config.get('config')
            )
            text = config.get('config')
        await call.message.answer_document(
            document=await str_to_file(
                file_name=file_name,
                text=text
            ),
            caption=caption,
            reply_markup = await instruction_manual(
                lang,
                key.server_table.type_vpn
            ),
            parse_mode=ParseMode.MARKDOWN
        )
        try:
            await call.message.delete()
        except Exception as e:
            log.info('Error delete message', exc_info=e)
            pass
    elif key.server_table.type_vpn == CONFIG.TypeVpn.REMNAWAVE.value:
        connect_message = _('how_to_connect_remnawave', lang).format(
            config=config,
        )
        await edit_message(
            call.message,
            photo=photo,
            caption=connect_message,
            reply_markup=await instruction_manual(
                lang,
                key.server_table.type_vpn,
                link_sub=config,
                key_id=key.id
            )
        )
    else:
        connect_message = _('how_to_connect', lang).format(
            name_vpn=ServerManager.VPN_TYPES.get(key.server_table.type_vpn)
            .NAME_VPN,
            config=config,
        )
        await edit_message(
            call.message,
            photo=photo,
            caption=connect_message,
            reply_markup=await instruction_manual(
                lang,
                key.server_table.type_vpn
            ),
            parse_mode=ParseMode.MARKDOWN
        )
    await call.answer()


async def get_img_type_vpn(key):
    if key.server_table.type_vpn == CONFIG.TypeVpn.OUTLINE.value:
        return 'bot/img/outline.jpg'
    if key.server_table.type_vpn == CONFIG.TypeVpn.VLESS.value:
        return 'bot/img/vless.jpg'
    if key.server_table.type_vpn == CONFIG.TypeVpn.SHADOW_SOCKS.value:
        return 'bot/img/shadow_socks.jpg'
    if key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
        return None
    if key.server_table.type_vpn == CONFIG.TypeVpn.AMNEZIA_WG.value:
        return None
    if key.server_table.type_vpn == CONFIG.TypeVpn.TROJAN.value:
        return 'bot/img/trojan.jpg'
    if key.server_table.type_vpn == CONFIG.TypeVpn.REMNAWAVE.value:
        return 'bot/img/remnawave.jpg'
    else:
        log.error('Unknown VPN type')
        return None



async def choosing_protocol_or_server(
    callback: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext,
    user_id: int,
    lang,
    key_id=0,
    back_data=None,
    payment:bool = False
) -> None:
    user = await get_person(session, user_id)
    all_types_vpn = await get_type_vpn(session, user.group)
    if len(all_types_vpn) != 1:
        await edit_message(
            callback.message,
            photo='bot/img/type_vpn.jpg',
            caption=_('choosing_connect_type', lang),
            reply_markup=await choose_type_vpn(
                all_types_vpn,
                lang,
                key_id=key_id,
                back_data=back_data,
                payment=payment
            )
        )
    else:
        try:
            all_active_location = await get_free_servers(
                session, user.group, all_types_vpn[0]
            )
        except FileNotFoundError:
            log.info('Not free servers -- OK')
            await callback.message.answer(_('not_server', lang))
            return
        if len(all_active_location) != 1:
            await edit_message(
                callback.message,
                photo='bot/img/locations.jpg',
                caption=_('choosing_connect_location', lang),
                reply_markup=await choose_server(
                    all_active_location,
                    all_types_vpn[0],
                    lang,
                    key_id,
                    payment=payment
                )
            )
        else:
            await select_location_callback(
                callback,
                session,
                callback_data=ChooseLocation(
                    id_location=all_active_location[0].id,
                    key_id=key_id,
                    type_vpn=all_types_vpn[0],
                    payment=payment
                ),
                js=js,
                remove_key_subject=remove_key_subject,
                state=state
            )


@get_key_router.callback_query(ShowUserDevices.filter())
async def show_user_devices_callback(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ShowUserDevices,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    key = await get_key_id(session, callback_data.key_id)
    try:
        server_manager = ServerManager(key.server_table, timeout=10)
        await server_manager.login()
        user_devices = await server_manager.get_user_devices(
            call.from_user.id, key.id
        )
    except Exception as e:
        log.error('Error get user device', exc_info=e)
        return

    list_devices = ''
    for device in user_devices:
        list_devices += f'\n🔹 {device.device_model}'
    if CONFIG.limit_ip == 0:
        limit = _('limit_ip_zero', lang)
    else:
        limit = CONFIG.limit_ip
    await edit_message(
        call.message,
        text=_('remnawave_user_devices', lang).format(
            limit_ip=limit,
            actual_count_device=len(user_devices),
            list_device=list_devices
        ),
        reply_markup=await user_device_remove(lang, key.id, user_devices)
    )


@get_key_router.callback_query(RemoveUserDevices.filter())
async def remove_user_devices_callback(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: RemoveUserDevices,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    key = await get_key_id(session, callback_data.key_id)
    try:
        server_manager = ServerManager(key.server_table, timeout=10)
        await server_manager.login()
        await server_manager.remove_user_devices(
            name=call.from_user.id,
            key_id=key.id,
            device_id=callback_data.hwid
        )
    except Exception as e:
        log.error('Error get user device', exc_info=e)
        return
    await edit_message(
        call.message,
        text=_('remove_device_success_btn', lang),
        reply_markup=await back_menu_button(lang)
    )

