from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.callbackData import BroadcastAction, BroadcastAudience


async def broadcast_audience_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="👥 All users",
        callback_data=BroadcastAudience(segment="all"),
    )
    kb.button(
        text="🟢 Active users",
        callback_data=BroadcastAudience(segment="active"),
    )
    kb.button(
        text="⚪ Users without subscription",
        callback_data=BroadcastAudience(segment="no_subscription"),
    )
    kb.button(
        text="🔴 Expired 3x-ui users",
        callback_data=BroadcastAudience(segment="expired_legacy"),
    )
    kb.button(
        text="↩️ Cancel",
        callback_data=BroadcastAction(action="cancel"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Send", callback_data=BroadcastAction(action="confirm"))
    kb.button(text="✏️ Edit text", callback_data=BroadcastAction(action="edit"))
    kb.button(text="❌ Cancel", callback_data=BroadcastAction(action="cancel"))
    kb.adjust(2, 1)
    return kb.as_markup()

