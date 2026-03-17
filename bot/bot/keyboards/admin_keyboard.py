from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.callbackData import BroadcastAction, BroadcastAudience
from bot.misc.language import Localization

_ = Localization.text


async def admin_dashboard_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_("admin_dash_btn_dashboard", lang),
        callback_data="admin_dash:dashboard",
    )
    kb.button(
        text=_("admin_dash_btn_users", lang),
        callback_data="admin_dash:users",
    )
    kb.button(
        text=_("admin_dash_btn_subscriptions", lang),
        callback_data="admin_dash:subscriptions",
    )
    kb.button(
        text=_("admin_dash_btn_servers", lang),
        callback_data="admin_dash:servers",
    )
    kb.button(
        text=_("admin_dash_btn_growth", lang),
        callback_data="admin_dash:growth",
    )
    kb.button(
        text=_("admin_dash_btn_revenue", lang),
        callback_data="admin_dash:revenue",
    )
    kb.button(
        text=_("admin_dash_btn_connections", lang),
        callback_data="admin_dash:connections",
    )
    kb.button(
        text=_("admin_dash_btn_referrals", lang),
        callback_data="admin_dash:referrals",
    )
    kb.button(
        text=_("admin_dash_btn_broadcast", lang),
        callback_data="admin_dash:broadcast",
    )
    kb.button(
        text=_("admin_dash_btn_errors", lang),
        callback_data="admin_dash:errors",
    )
    kb.button(
        text=_("admin_dash_btn_migration", lang),
        callback_data="admin_dash:migration",
    )
    kb.adjust(1)
    return kb.as_markup()


async def admin_dashboard_back_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_("admin_dash_back_btn", lang),
        callback_data="admin_dash:home",
    )
    kb.adjust(1)
    return kb.as_markup()


async def broadcast_audience_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_("admin_broadcast_all_users_btn", lang),
        callback_data=BroadcastAudience(segment="all"),
    )
    kb.button(
        text=_("admin_broadcast_active_users_btn", lang),
        callback_data=BroadcastAudience(segment="active"),
    )
    kb.button(
        text=_("admin_broadcast_no_sub_users_btn", lang),
        callback_data=BroadcastAudience(segment="no_subscription"),
    )
    kb.button(
        text=_("admin_broadcast_expired_legacy_btn", lang),
        callback_data=BroadcastAudience(segment="expired_legacy"),
    )
    kb.button(
        text=_("admin_broadcast_cancel_btn", lang),
        callback_data=BroadcastAction(action="cancel"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def broadcast_confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_("admin_broadcast_send_btn", lang),
        callback_data=BroadcastAction(action="confirm"),
    )
    kb.button(
        text=_("admin_broadcast_edit_btn", lang),
        callback_data=BroadcastAction(action="edit"),
    )
    kb.button(
        text=_("admin_broadcast_cancel_btn", lang),
        callback_data=BroadcastAction(action="cancel"),
    )
    kb.adjust(2, 1)
    return kb.as_markup()
