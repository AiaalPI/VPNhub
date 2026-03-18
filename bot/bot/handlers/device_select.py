from bot.keyboards.device_keyboard import device_select_keyboard
from bot.misc.language import Localization
from bot.services.message_render_service import edit_message

_ = Localization.text


def _device_caption(lang: str) -> str:
    text = _("marzban_choose_device_message", lang)
    if not text or text == "marzban_choose_device_message":
        return "Выберите устройство для подключения:"
    return text


async def show_device_selection(
    message,
    lang: str,
    key_id: int,
) -> None:
    await edit_message(
        message,
        photo="bot/img/marzban.jpg",
        caption=_device_caption(lang),
        reply_markup=await device_select_keyboard(lang, key_id),
    )
