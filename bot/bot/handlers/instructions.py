import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_key_id
from bot.keyboards.device_keyboard import (
    device_instruction_keyboard,
    device_select_keyboard,
)
from bot.misc.callbackData import CopySubscription, MarzbanDevice
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.service.edit_message import edit_message
from bot.services.subscription_service import get_user_subscription_link
from bot.utils.text_templates import device_instruction_message_key

instructions_router = Router()
log = logging.getLogger(__name__)
_ = Localization.text


@instructions_router.callback_query(MarzbanDevice.filter())
async def marzban_device_selected(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: MarzbanDevice,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    key = await get_key_id(session, callback_data.key_id)
    if key is None or key.server is None:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return
    if int(key.user_tgid) != int(call.from_user.id):
        await call.answer(_("error_send_admin", lang), show_alert=True)
        return
    if int(key.server_table.type_vpn) != CONFIG.TypeVpn.MARZBAN.value:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return

    if callback_data.device == "back":
        await edit_message(
            call.message,
            photo="bot/img/marzban.jpg",
            caption=_("marzban_choose_device_message", lang),
            reply_markup=await device_select_keyboard(lang, key.id),
        )
        await call.answer()
        return

    subscription_link = await get_user_subscription_link(
        session=session,
        key_id=key.id,
        user_id=call.from_user.id,
    )
    if not subscription_link:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return

    instruction_key = device_instruction_message_key(callback_data.device)
    await edit_message(
        call.message,
        photo="bot/img/marzban.jpg",
        caption=_(instruction_key, lang).format(config=subscription_link),
        reply_markup=await device_instruction_keyboard(
            lang=lang,
            key_id=key.id,
            device=callback_data.device,
            subscription_link=subscription_link,
        ),
    )
    await call.answer()


@instructions_router.callback_query(CopySubscription.filter())
async def marzban_copy_subscription(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: CopySubscription,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    key = await get_key_id(session, callback_data.key_id)
    if key is None or key.server is None:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return
    if int(key.user_tgid) != int(call.from_user.id):
        await call.answer(_("error_send_admin", lang), show_alert=True)
        return
    if int(key.server_table.type_vpn) != CONFIG.TypeVpn.MARZBAN.value:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return
    subscription_link = await get_user_subscription_link(
        session=session,
        key_id=key.id,
        user_id=call.from_user.id,
    )
    if not subscription_link:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return
    await call.message.answer(
        _("subscription_link_copy_message", lang).format(config=subscription_link)
    )
    await call.answer()
