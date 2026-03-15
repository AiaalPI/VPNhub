from bot.misc.language import Localization

_ = Localization.text


def migration_message(lang: str) -> str:
    return _("migration_expired_message", lang)


def device_instruction_message_key(device: str) -> str:
    return {
        "iphone": "marzban_device_instruction_iphone",
        "android": "marzban_device_instruction_android",
        "windows": "marzban_device_instruction_windows",
        "macos": "marzban_device_instruction_macos",
    }.get(device, "marzban_device_instruction_android")

