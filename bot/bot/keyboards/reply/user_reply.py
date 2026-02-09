from aiogram.types import ReplyKeyboardMarkup, KeyboardButton as keyBtn
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from bot.misc.language import Localization

_ = Localization.text

async def main_menu(lang) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(keyBtn(text=_('general_menu_btn', lang)))
    return kb.as_markup(resize_keyboard=True)
