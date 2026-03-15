from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.callbackData import CopySubscription, MarzbanDevice
from bot.misc.language import Localization
from bot.utils.deeplink import resolve_device_connect_link

_ = Localization.text


def _device_meta(device: str, lang: str) -> dict:
    if device == "iphone":
        return {
            "download_url": "https://apps.apple.com/app/streisand/id6450534064",
            "download_btn": _("marzban_download_streisand_btn", lang),
            "manual_btn": _("instruction_use_iphone_btn", lang),
            "manual_url": _("instruction_iphone_marzban", lang, False),
        }
    if device == "android":
        return {
            "download_url": "https://play.google.com/store/apps/details?id=app.hiddify.com",
            "download_btn": _("marzban_download_hiddify_btn", lang),
            "manual_btn": _("instruction_use_android_btn", lang),
            "manual_url": _("instruction_android_marzban", lang, False),
        }
    if device == "windows":
        return {
            "download_url": "https://github.com/hiddify/hiddify-app/releases",
            "download_btn": _("marzban_download_hiddify_btn", lang),
            "manual_btn": _("instruction_use_pc_btn", lang),
            "manual_url": _("instruction_windows_marzban", lang, False),
        }
    return {
        "download_url": "https://github.com/hiddify/hiddify-app/releases",
        "download_btn": _("marzban_download_hiddify_btn", lang),
        "manual_btn": _("instruction_use_mac_btn", lang),
        "manual_url": _("instruction_mac_marzban", lang, False),
    }


async def device_select_keyboard(lang: str, key_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_("marzban_device_iphone_btn", lang),
        callback_data=MarzbanDevice(key_id=key_id, device="iphone"),
    )
    kb.button(
        text=_("marzban_device_android_btn", lang),
        callback_data=MarzbanDevice(key_id=key_id, device="android"),
    )
    kb.button(
        text=_("marzban_device_windows_btn", lang),
        callback_data=MarzbanDevice(key_id=key_id, device="windows"),
    )
    kb.button(
        text=_("marzban_device_macos_btn", lang),
        callback_data=MarzbanDevice(key_id=key_id, device="macos"),
    )
    kb.button(
        text=_("back_general_menu_btn", lang),
        callback_data="answer_back_general_menu_btn",
    )
    kb.adjust(1)
    return kb.as_markup()


async def device_instruction_keyboard(
    lang: str,
    key_id: int,
    device: str,
    subscription_link: str,
) -> InlineKeyboardMarkup:
    meta = _device_meta(device, lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=meta["download_btn"], url=meta["download_url"])
    kb.button(
        text=_("marzban_connect_btn", lang),
        url=resolve_device_connect_link(device, subscription_link),
    )
    kb.button(
        text=_("copy_subscription_btn", lang),
        callback_data=CopySubscription(key_id=key_id),
    )
    kb.button(text=meta["manual_btn"], url=meta["manual_url"])
    kb.button(
        text=_("back_type_vpn", lang),
        callback_data=MarzbanDevice(key_id=key_id, device="back"),
    )
    kb.adjust(1)
    return kb.as_markup()
