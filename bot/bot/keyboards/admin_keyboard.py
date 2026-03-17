from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.callbackData import BroadcastAction, BroadcastAudience
from bot.misc.language import Localization

_ = Localization.text


def _t(key: str, lang: str, default: str) -> str:
    text = _(key, lang)
    if not text or text == key:
        return default
    return text


async def admin_dashboard_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_dash_btn_dashboard", lang, "📊 Дашборд"),
        callback_data="admin_dash:dashboard",
    )
    kb.button(
        text=_t("admin_dash_btn_users", lang, "👥 Пользователи"),
        callback_data="admin_dash:users",
    )
    kb.button(
        text=_t("admin_dash_btn_subscriptions", lang, "💳 Подписки"),
        callback_data="admin_dash:subscriptions",
    )
    kb.button(
        text=_t("admin_dash_btn_servers", lang, "🌍 Серверы"),
        callback_data="admin_dash:servers",
    )
    kb.button(
        text=_t("admin_dash_btn_growth", lang, "📈 Рост"),
        callback_data="admin_dash:growth",
    )
    kb.button(
        text=_t("admin_dash_btn_revenue", lang, "💰 Выручка"),
        callback_data="admin_dash:revenue",
    )
    kb.button(
        text=_t("admin_dash_btn_connections", lang, "🔌 Подключения"),
        callback_data="admin_dash:connections",
    )
    kb.button(
        text=_t("admin_dash_btn_referrals", lang, "🎁 Рефералы"),
        callback_data="admin_dash:referrals",
    )
    kb.button(
        text=_t("admin_dash_btn_broadcast", lang, "📢 Рассылка"),
        callback_data="admin_dash:broadcast",
    )
    kb.button(
        text=_t("admin_dash_btn_errors", lang, "⚠️ Ошибки"),
        callback_data="admin_dash:errors",
    )
    kb.button(
        text=_t("admin_dash_btn_migration", lang, "🔄 Миграция"),
        callback_data="admin_dash:migration",
    )
    kb.adjust(1)
    return kb.as_markup()


async def admin_dashboard_back_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_dash_back_btn", lang, "⬅️ Назад в админ-панель"),
        callback_data="admin_dash:home",
    )
    kb.adjust(1)
    return kb.as_markup()


async def broadcast_audience_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_broadcast_all_users_btn", lang, "👥 Все пользователи"),
        callback_data=BroadcastAudience(segment="all"),
    )
    kb.button(
        text=_t("admin_broadcast_active_users_btn", lang, "🟢 Активные пользователи"),
        callback_data=BroadcastAudience(segment="active"),
    )
    kb.button(
        text=_t("admin_broadcast_no_sub_users_btn", lang, "⚪ Пользователи без подписки"),
        callback_data=BroadcastAudience(segment="no_subscription"),
    )
    kb.button(
        text=_t("admin_broadcast_expired_legacy_btn", lang, "🔴 Истёкшие 3x-ui"),
        callback_data=BroadcastAudience(segment="expired_legacy"),
    )
    kb.button(
        text=_t("admin_broadcast_cancel_btn", lang, "↩️ Отмена"),
        callback_data=BroadcastAction(action="cancel"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def broadcast_confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_broadcast_send_btn", lang, "✅ Отправить"),
        callback_data=BroadcastAction(action="confirm"),
    )
    kb.button(
        text=_t("admin_broadcast_edit_btn", lang, "✏️ Изменить текст"),
        callback_data=BroadcastAction(action="edit"),
    )
    kb.button(
        text=_t("admin_broadcast_cancel_btn", lang, "↩️ Отмена"),
        callback_data=BroadcastAction(action="cancel"),
    )
    kb.adjust(2, 1)
    return kb.as_markup()
