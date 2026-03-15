from aiogram import Bot

from bot.keyboards.connect_keyboard import migration_connect_keyboard
from bot.misc.language import Localization

_ = Localization.text


async def send_migration_prompt(bot: Bot, user_id: int, lang: str) -> None:
    await bot.send_message(
        user_id,
        _("migration_expired_message", lang),
        disable_web_page_preview=True,
        reply_markup=await migration_connect_keyboard(lang),
    )

