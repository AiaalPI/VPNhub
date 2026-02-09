from datetime import datetime

from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.types import Message, Chat, User


async def get_message(
    bot: Bot,
    user_telegram_id: int,
    message_id: int=1
) -> Message:
    chat = Chat(id=user_telegram_id, type=ChatType.PRIVATE)
    user = User(id=user_telegram_id, is_bot=False, first_name="User")
    message = Message(
        message_id=message_id,
        chat=chat,
        from_user=user,
        date=datetime.now(),
    )
    message._bot = bot
    return message
