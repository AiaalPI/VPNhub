from bot.keyboards.device_keyboard import device_select_keyboard
from bot.misc.language import Localization
from bot.service.edit_message import edit_message

_ = Localization.text


async def show_device_selection(
    message,
    lang: str,
    key_id: int,
) -> None:
    await edit_message(
        message,
        photo="bot/img/marzban.jpg",
        caption=_("marzban_choose_device_message", lang),
        reply_markup=await device_select_keyboard(lang, key_id),
    )

