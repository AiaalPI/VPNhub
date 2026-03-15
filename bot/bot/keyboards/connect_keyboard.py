from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.language import Localization

_ = Localization.text


async def migration_connect_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_("migration_connect_btn", lang),
        callback_data="vpn_connect_btn",
    )
    kb.adjust(1)
    return kb.as_markup()
