import logging

from aiogram.enums import ParseMode
from aiogram.types import Message, InputMediaPhoto, FSInputFile

from bot.misc.language import Localization

_ = Localization.text
log = logging.getLogger(__name__)


async def edit_message(
    message: Message,
    photo=None,
    caption=None,
    reply_markup=None,
    text=None,
    parse_mode=ParseMode.HTML,
):
    try:
        if photo is not None:
            await message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(photo)
                )
            )
        if text is not None:
            await message.edit_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            return
        await message.edit_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        if photo is not None:
            await message.answer_photo(
                photo=FSInputFile(photo),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif caption is not None:
            await message.answer(
                text=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            await message.answer(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
