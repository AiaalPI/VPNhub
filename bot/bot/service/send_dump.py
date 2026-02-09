import logging

from aiogram import Bot
from aiogram.types import FSInputFile

from bot.database.methods.get import dump_postgres_db
from bot.misc.language import Localization
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

_ = Localization.text


async def send_dump(bot: Bot):
    try:
        await dump_postgres_db()
        await bot.send_document(
            chat_id=CONFIG.admin_tg_id,
            document=FSInputFile('./logs/db_dumps/BotDataBase.dump'),
            caption=_('dump_message', CONFIG.languages)
        )
    except Exception as e:
        log.error(e)