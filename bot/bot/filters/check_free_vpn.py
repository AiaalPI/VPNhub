from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.misc.language import Localization
from bot.misc.util import CONFIG

_ = Localization.text


class IsWorkFreeVPN(Filter):
    def __init__(self):
        self.free_vpn_work = CONFIG.free_vpn

    async def __call__(self, call: CallbackQuery, state: FSMContext) -> bool:
        return self.free_vpn_work
