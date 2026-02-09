import gettext
import re
from dataclasses import dataclass
from pathlib import Path

from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_person_lang
from bot.misc.util import CONFIG

default_font = (
    'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'
    'абвгдеёжзийклмнопрстуфхцчшщъыьэюя'
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
    '0123456789'
)


async def get_lang(session: AsyncSession, user_id: int, state: FSMContext=None):
    if state is not None:
        data = await state.get_data()
        lang = data.get('lang')
        if lang is None:
            lang = await get_person_lang(session, user_id)
            await state.update_data(lang=lang)
        return lang
    else:
        return await get_person_lang(session, user_id)


@dataclass
class Localization:
    ALL_Languages = {
        'en': '🇬🇧 Ꭼnglish',
        'ru': '🇷🇺 Ꮲуᴄᴄᴋий'
    }
    PATH = Path(__file__).resolve().parent.parent / 'locale'

    @classmethod
    def font_text(cls, text):
        if CONFIG.font_template != '':
            template = CONFIG.font_template
        else:
            template = default_font
        font_map = str.maketrans(
            default_font,
            template
        )

        def replace(match):
            content = match.group(0)
            if content.startswith('<') and content.endswith('>'):
                return content
            if content.startswith('{') and content.endswith('}'):
                return content
            return content.translate(font_map)

        return re.sub(r'<[^>]*>|{[^}]*}|[^<{]+', replace, text)

    @classmethod
    def get_reply_button(cls, key_text) -> list:
        buttons_text = []
        for lang_key in cls.ALL_Languages.keys():
            lang = gettext.translation(
                'bot',
                localedir=cls.PATH,
                languages=[lang_key]
            )
            lang.install()
            buttons_text.append(cls.font_text(lang.gettext(key_text)))
        return buttons_text

    @classmethod
    def text(cls, key_text, language=CONFIG.languages, font=True):
        lang = gettext.translation(
            'bot',
            localedir=cls.PATH,
            languages=[language]
        )
        lang.install()
        if font:
            return cls.font_text(lang.gettext(key_text))
        else:
            return lang.gettext(key_text)
