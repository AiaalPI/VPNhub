import logging
import time

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_key_id, get_key_user
from bot.keyboards.device_keyboard import (
    device_instruction_keyboard,
    device_select_keyboard,
)
from bot.misc.callbackData import CopySubscription, MarzbanDevice
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.services.message_render_service import edit_message
from bot.services.subscription_service import get_user_subscription_link
from bot.utils.text_templates import device_instruction_message_key

instructions_router = Router()
log = logging.getLogger(__name__)
_ = Localization.text


def _t(key: str, lang: str, default: str) -> str:
    text = _(key, lang)
    if not text or text == key:
        return default
    return text


def _copy_subscription_message(lang: str, subscription_link: str) -> str:
    template = _("subscription_link_copy_message", lang)
    if not template or template == "subscription_link_copy_message":
        if lang == "en":
            return f"📋 Connection link:\n{subscription_link}"
        return f"📋 Ссылка для подключения:\n{subscription_link}"
    return template.format(config=subscription_link)


def _fallback_instruction(device: str, subscription_link: str, lang: str) -> str:
    if lang == "en":
        return (
            "Install VPN app, tap connect button below, "
            "or copy this link and import manually:\n"
            f"{subscription_link}"
        )
    return (
        "Установите VPN-приложение, нажмите кнопку подключения ниже, "
        "или скопируйте ссылку и импортируйте вручную:\n"
        f"{subscription_link}"
    )


async def _resolve_user_marzban_key(session: AsyncSession, user_id: int):
    keys = await get_key_user(session, user_id)
    marzban_keys = [
        key for key in keys
        if (
            getattr(key, "server_table", None) is not None
            and int(getattr(key.server_table, "type_vpn", -1)) == CONFIG.TypeVpn.MARZBAN.value
        )
    ]
    if not marzban_keys:
        return None
    now_ts = int(time.time())
    active = [
        key for key in marzban_keys
        if int(getattr(key, "subscription", 0) or 0) > now_ts
    ]
    pool = active or marzban_keys
    return max(
        pool,
        key=lambda key: (
            int(getattr(key, "subscription", 0) or 0),
            int(getattr(key, "id", 0) or 0),
        ),
    )


@instructions_router.callback_query(MarzbanDevice.filter())
async def marzban_device_selected(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: MarzbanDevice,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    key = await get_key_id(session, callback_data.key_id)
    if (
        key is None
        or key.server is None
        or int(getattr(key, "user_tgid", 0) or 0) != int(call.from_user.id)
        or int(getattr(key.server_table, "type_vpn", -1)) != CONFIG.TypeVpn.MARZBAN.value
    ):
        key = await _resolve_user_marzban_key(session, call.from_user.id)
    if key is None or key.server is None:
        await call.answer(_("server_not_connected", lang), show_alert=True)
        return

    if callback_data.device == "back":
        await edit_message(
            call.message,
            photo="bot/img/marzban.jpg",
            caption=_t("marzban_choose_device_message", lang, "Выберите устройство для подключения:"),
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
    instruction_text = _(instruction_key, lang)
    if not instruction_text or instruction_text == instruction_key:
        instruction_text = _fallback_instruction(callback_data.device, subscription_link, lang)
    await edit_message(
        call.message,
        photo="bot/img/marzban.jpg",
        caption=instruction_text.format(config=subscription_link),
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
    if (
        key is None
        or key.server is None
        or int(getattr(key, "user_tgid", 0) or 0) != int(call.from_user.id)
        or int(getattr(key.server_table, "type_vpn", -1)) != CONFIG.TypeVpn.MARZBAN.value
    ):
        key = await _resolve_user_marzban_key(session, call.from_user.id)
    if key is None or key.server is None:
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
    await call.message.answer(_copy_subscription_message(lang, subscription_link))
    await call.answer()
