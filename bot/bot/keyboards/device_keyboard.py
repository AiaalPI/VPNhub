from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.callbackData import CopySubscription, MarzbanDevice
from bot.misc.language import Localization
from bot.utils.deeplink import resolve_device_connect_link

_ = Localization.text

OLD_INSTRUCTION_IPHONE = (
    "https://telegra.ph/Instrukciya-po-podklyucheniyu-VPN-"
    "Vless-i-ShadowSocks-dlya-IPhone-08-25"
)
OLD_INSTRUCTION_ANDROID = (
    "https://telegra.ph/Instrukciya-po-podklyucheniyu-VPN-"
    "Vless-dlya-Android-05-01"
)
OLD_INSTRUCTION_WINDOWS = (
    "https://telegra.ph/Instrukciya-po-podklyucheniyu-VPN-"
    "Vless-i-ShadowSocks-dlya-PK-11-28-3"
)


def _t(key: str, lang: str, default: str) -> str:
    text = _(key, lang)
    if not text or text == key:
        return default
    return text


def _device_meta(device: str, lang: str) -> dict:
    if device == "iphone":
        return {
            "download_url": "https://apps.apple.com/app/streisand/id6450534064",
            "download_btn": _t("marzban_download_streisand_btn", lang, "⬇️ Скачать Streisand"),
            "manual_btn": _t("instruction_use_iphone_btn", lang, "Инструкция для iOS"),
            "manual_url": OLD_INSTRUCTION_IPHONE,
        }
    if device == "android":
        return {
            "download_url": "https://play.google.com/store/apps/details?id=app.hiddify.com",
            "download_btn": _t("marzban_download_hiddify_btn", lang, "⬇️ Скачать Hiddify"),
            "manual_btn": _t("instruction_use_android_btn", lang, "Инструкция для Android"),
            "manual_url": OLD_INSTRUCTION_ANDROID,
        }
    if device == "windows":
        return {
            "download_url": "https://github.com/hiddify/hiddify-app/releases",
            "download_btn": _t("marzban_download_hiddify_btn", lang, "⬇️ Скачать Hiddify"),
            "manual_btn": _t("instruction_use_pc_btn", lang, "Инструкция для Windows"),
            "manual_url": OLD_INSTRUCTION_WINDOWS,
        }
    return {
        "download_url": "https://github.com/hiddify/hiddify-app/releases",
        "download_btn": _t("marzban_download_hiddify_btn", lang, "⬇️ Скачать Hiddify"),
        "manual_btn": _t("instruction_use_mac_btn", lang, "Инструкция для macOS"),
        # Old Mac telegraph URL is 404; use working desktop Hiddify instruction.
        "manual_url": OLD_INSTRUCTION_WINDOWS,
    }


async def device_select_keyboard(lang: str, key_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("marzban_device_iphone_btn", lang, "📱 iPhone / iPad"),
        callback_data=MarzbanDevice(key_id=key_id, device="iphone"),
    )
    kb.button(
        text=_t("marzban_device_android_btn", lang, "🤖 Android"),
        callback_data=MarzbanDevice(key_id=key_id, device="android"),
    )
    kb.button(
        text=_t("marzban_device_windows_btn", lang, "💻 Windows"),
        callback_data=MarzbanDevice(key_id=key_id, device="windows"),
    )
    kb.button(
        text=_t("marzban_device_macos_btn", lang, "🍏 macOS"),
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
        text=_t("marzban_connect_btn", lang, "🚀 Подключить VPN"),
        url=resolve_device_connect_link(device, subscription_link),
    )
    kb.button(
        text=_t("copy_subscription_btn", lang, "📋 Скопировать ссылку"),
        callback_data=CopySubscription(key_id=key_id),
    )
    kb.button(text=meta["manual_btn"], url=meta["manual_url"])
    kb.button(
        text=_("back_type_vpn", lang),
        callback_data=MarzbanDevice(key_id=key_id, device="back"),
    )
    kb.adjust(1)
    return kb.as_markup()
