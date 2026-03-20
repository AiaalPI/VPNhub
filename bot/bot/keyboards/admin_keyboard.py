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


async def admin_growth_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_metrics_list_btn", lang, "📊 Метрики"),
        callback_data="admin_metrics:list",
    )
    kb.button(
        text=_t("admin_metrics_stats_btn", lang, "📄 Статистика метрик"),
        callback_data="admin_metrics:stats",
    )
    kb.button(
        text=_t("admin_dash_back_btn", lang, "⬅️ Назад в админ-панель"),
        callback_data="admin_dash:home",
    )
    kb.adjust(1)
    return kb.as_markup()


async def admin_infra_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_infra_locations_btn", lang, "🌍 Локации и VDS"),
        callback_data="admin_infra:locations",
    )
    kb.button(
        text=_t("admin_infra_static_add_btn", lang, "➕ Статический пользователь"),
        callback_data="admin_infra:static_add",
    )
    kb.button(
        text=_t("admin_infra_static_list_btn", lang, "📄 Статические пользователи"),
        callback_data="admin_infra:static_list",
    )
    kb.button(
        text=_t("admin_infra_capacity_btn", lang, "📦 Экспорт емкости"),
        callback_data="locations_statistic",
    )
    kb.button(
        text=_t("admin_dash_back_btn", lang, "⬅️ Назад в админ-панель"),
        callback_data="admin_dash:home",
    )
    kb.adjust(1)
    return kb.as_markup()


async def admin_static_users_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_static_add_inline_btn", lang, "➕ Добавить статического пользователя"),
        callback_data="admin_infra:static_add",
    )
    kb.button(
        text=_t("admin_static_list_inline_btn", lang, "📄 Показать статических пользователей"),
        callback_data="admin_infra:static_list",
    )
    kb.button(
        text=_t("admin_infra_back_btn", lang, "⬅️ В инфраструктуру"),
        callback_data="admin_dash:servers",
    )
    kb.adjust(1)
    return kb.as_markup()


async def admin_users_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_users_find_btn", lang, "🔎 Найти пользователя"),
        callback_data="admin_users:find",
    )
    kb.button(
        text=_t("admin_users_all_export_btn", lang, "📄 Все пользователи"),
        callback_data="admin_users:all_export",
    )
    kb.button(
        text=_t("admin_users_paid_export_btn", lang, "💳 Платные пользователи"),
        callback_data="admin_users:paid_export",
    )
    kb.button(
        text=_t("admin_users_payments_export_btn", lang, "💰 Платежи"),
        callback_data="admin_users:payments_export",
    )
    kb.button(
        text=_t("admin_users_ref_export_btn", lang, "🎁 Реферальный отчет"),
        callback_data="admin_users:ref_export",
    )
    kb.button(
        text=_t("admin_users_refresh_btn", lang, "📊 Обновить сводку"),
        callback_data="admin_dash:users",
    )
    kb.button(
        text=_t("admin_dash_back_btn", lang, "⬅️ Назад в админ-панель"),
        callback_data="admin_dash:home",
    )
    kb.adjust(1, 2, 2, 1, 1)
    return kb.as_markup()


async def admin_referrals_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_promo_btn", lang, "🏷 Промокоды"),
        callback_data="admin_referrals:promo",
    )
    kb.button(
        text=_t("admin_reff_system_btn", lang, "🎁 Рефералы"),
        callback_data="admin_referrals:withdrawals",
    )
    kb.button(
        text=_t("admin_dash_back_btn", lang, "⬅️ Назад в админ-панель"),
        callback_data="admin_dash:home",
    )
    kb.adjust(1)
    return kb.as_markup()


async def admin_groups_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_groups_show_btn", lang, "📄 Показать группы"),
        callback_data="admin_groups:show",
    )
    kb.button(
        text=_t("admin_groups_add_btn", lang, "➕ Добавить группу"),
        callback_data="admin_groups:add",
    )
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
        text=_t("admin_broadcast_back_admin_btn", lang, "⬅️ В админ-панель"),
        callback_data=BroadcastAction(action="back_admin"),
    )
    kb.adjust(1)
    return kb.as_markup()


async def broadcast_waiting_text_keyboard(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t("admin_broadcast_change_audience_btn", lang, "👥 Сменить аудиторию"),
        callback_data=BroadcastAction(action="back_audience"),
    )
    kb.button(
        text=_t("admin_broadcast_back_admin_btn", lang, "⬅️ В админ-панель"),
        callback_data=BroadcastAction(action="back_admin"),
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
        text=_t("admin_broadcast_change_audience_btn", lang, "👥 Сменить аудиторию"),
        callback_data=BroadcastAction(action="back_audience"),
    )
    kb.button(
        text=_t("admin_broadcast_back_admin_btn", lang, "⬅️ В админ-панель"),
        callback_data=BroadcastAction(action="back_admin"),
    )
    kb.adjust(2, 1, 1)
    return kb.as_markup()
