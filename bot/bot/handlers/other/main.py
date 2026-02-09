import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import  Message, FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_person
from bot.filters.main import IsBlocked
from bot.keyboards.inline.user_inline import  user_menu

from bot.misc.language import Localization, get_lang

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

other_router = Router()
other_router.message.filter(IsBlocked())


@other_router.message()
async def other_message(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    person = await get_person(session, message.from_user.id)
    if person is None:
        return
    await message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(lang, person.tgid)
    )