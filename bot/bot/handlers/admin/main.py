import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.filters.main import IsAdmin
from bot.database.methods.get import (
    get_all_user,
    get_all_subscription,
    get_no_subscription,
)
from bot.handlers.admin_dashboard import admin_dashboard_router
from bot.handlers.admin_users import admin_users_router
from bot.handlers.admin_subscriptions import admin_subscriptions_router
from bot.handlers.admin_servers import admin_servers_router
from bot.handlers.admin_connections import admin_connections_router
from bot.handlers.admin_migration import admin_migration_router
from bot.handlers.admin_errors import admin_errors_router
from bot.handlers.admin.group_mangment import group_management
from bot.handlers.admin.keys_control import keys_control_router
from bot.handlers.admin.location_control import location_control
from bot.handlers.admin.metric_management import (
    metric_management_router,
    message_show_list_metrics,
)
from bot.handlers.admin.referal_admin import referral_router
from bot.handlers.admin.static_user_control import static_user
from bot.handlers.admin.user_management import (
    user_management_router,
)
from bot.handlers.admin_broadcast import admin_broadcast_router, BroadcastStates
from bot.handlers.admin.protocol_control import (
    state_admin_router,
)
from bot.keyboards.inline.admin_inline import (
    missing_user_menu,
    buttons_mailing
)
from bot.keyboards.admin_keyboard import (
    admin_dashboard_keyboard,
    admin_dashboard_back_keyboard,
    admin_growth_keyboard,
    broadcast_audience_keyboard,
)
from bot.keyboards.inline.user_inline import mailing_button_message
from bot.keyboards.reply.admin_reply import (
    admin_menu,
    back_admin_menu,
    show_user_menu,
)
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.misc.callbackData import (
    MissingMessage,
    ButtonsMailing
)
from bot.services.admin_summary_service import (
    get_growth_summary,
    get_referral_summary,
    get_revenue_summary,
)
from bot.services.message_render_service import edit_message

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

admin_router = Router()
admin_router.message.filter(IsAdmin())
admin_router.include_routers(
    admin_dashboard_router,
    admin_users_router,
    admin_subscriptions_router,
    admin_servers_router,
    admin_connections_router,
    admin_migration_router,
    admin_errors_router,
    user_management_router,
    admin_broadcast_router,
    location_control,
    state_admin_router,
    referral_router,
    group_management,
    keys_control_router,
    static_user,
    metric_management_router
)


class StateMailing(StatesGroup):
    input_text = State()


def _t(key: str, lang: str, default: str) -> str:
    text = _(key, lang)
    if not text or text == key:
        return default
    return text


def _money(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}"


async def _open_admin_dashboard(
    message: Message,
    lang: str,
    state: FSMContext
) -> None:
    await message.answer(
        _t('admin_dashboard_title', lang, '⚙️ KYNVPN Control Center'),
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        _t('admin_dashboard_title', lang, '⚙️ KYNVPN Control Center'),
        reply_markup=await admin_dashboard_keyboard(lang)
    )
    await state.clear()


@admin_router.message(Command('admin'))
async def admin_panel_command(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await _open_admin_dashboard(message, lang, state)


@admin_router.message(
    (F.text.in_(btn_text('admin_panel_btn'))) |
    (F.text.in_(btn_text('admin_back_admin_menu_btn')))
)
async def admin_panel(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await _open_admin_dashboard(message, lang, state)


@admin_router.callback_query(F.data == 'admin_panel_btn')
async def admin_panel_callback(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    if not CONFIG.is_admin(call.from_user.id):
        return
    await _open_admin_dashboard(call.message, lang, state)
    await call.answer()


@admin_router.callback_query(
    F.data.startswith('admin_dash:') &
    ~F.data.in_({
        'admin_dash:dashboard',
        'admin_dash:home',
        'admin_dash:users',
        'admin_dash:subscriptions',
        'admin_dash:servers',
        'admin_dash:connections',
        'admin_dash:migration',
        'admin_dash:errors',
    })
)
async def admin_dashboard_sections(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    if not CONFIG.is_admin(call.from_user.id):
        return
    lang = await get_lang(session, call.from_user.id, state)
    section = call.data.split(':', maxsplit=1)[1]

    if section == 'growth':
        summary = await get_growth_summary(session)
        await edit_message(
            call.message,
            text=_('admin_growth_summary_text', lang).format(
                metrics_count=summary.metrics_count,
                users_with_metric=summary.users_with_metric,
                referrals_attached=summary.referrals_attached,
                users_30_days=summary.users_30_days,
            ),
            reply_markup=await admin_growth_keyboard(lang)
        )
        await call.answer()
        return

    if section == 'revenue':
        summary = await get_revenue_summary(session)
        await edit_message(
            call.message,
            text=_('admin_revenue_summary_text', lang).format(
                successful_payments_today=summary.successful_payments_today,
                revenue_today=_money(summary.revenue_today),
                revenue_7_days=_money(summary.revenue_7_days),
                revenue_30_days=_money(summary.revenue_30_days),
            ),
            reply_markup=await admin_dashboard_back_keyboard(lang)
        )
        await call.answer()
        return

    if section == 'referrals':
        summary = await get_referral_summary(session)
        await edit_message(
            call.message,
            text=_('admin_referrals_summary_text', lang).format(
                total_referrers=summary.total_referrers,
                invited_users=summary.invited_users,
                paid_referrals=summary.paid_referrals,
                pending_withdrawals=summary.pending_withdrawals,
            ),
            reply_markup=await admin_dashboard_back_keyboard(lang)
        )
        await call.answer()
        return

    if section == 'broadcast':
        await state.clear()
        await state.set_state(BroadcastStates.waiting_audience)
        await call.message.answer(
            _('admin_broadcast_choose_audience', lang),
            reply_markup=await broadcast_audience_keyboard(lang),
        )
        await call.answer()
        return

    section_defaults = {
        'dashboard': '📊 Дашборд',
        'users': '👥 Пользователи',
        'subscriptions': '💳 Подписки',
        'servers': '🌍 Серверы',
        'growth': '📈 Рост',
        'revenue': '💰 Выручка',
        'connections': '🔌 Подключения',
        'referrals': '🎁 Рефералы',
        'broadcast': '📢 Рассылка',
        'errors': '⚠️ Ошибки',
        'migration': '🔄 Миграция',
    }
    await call.message.answer(
        _t(
            'admin_dash_placeholder',
            lang,
            'Раздел {section} будет вынесен в отдельный дашборд. Текущая админ-логика сохранена.'
        ).format(
            section=_t(
                'admin_dash_btn_' + section,
                lang,
                section_defaults.get(section, section),
            )
        ),
        reply_markup=await admin_dashboard_back_keyboard(lang)
    )
    await call.answer()


@admin_router.message(F.text.in_(btn_text('admin_send_message_users_btn')))
async def out_message_bot(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('who_should_i_send', lang),
        reply_markup=await missing_user_menu(lang)
    )


@admin_router.callback_query(MissingMessage.filter())
async def update_message_bot(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: MissingMessage,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.option == 'update':
        try:
            users = await get_all_user(session)
            await update_client(call.message, users, lang)
        except Exception as e:
            await call.message.answer(_('error_update', lang))
            log.error('not update menu all users', exc_info=e)
        await call.answer()
        return
    await state.update_data(option=callback_data.option)
    await edit_message(
        call.message,
        text=_('want_attach_button_mailing', lang),
        reply_markup=await buttons_mailing(lang, CONFIG)
    )


@admin_router.callback_query(ButtonsMailing.filter())
async def message_buttons_mailing(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ButtonsMailing,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await state.update_data(button=callback_data.action)
    await call.message.delete()
    await call.message.answer(
        _('input_message_or_image', lang),
        reply_markup=await back_admin_menu(lang)
    )
    await call.answer()
    await state.set_state(StateMailing.input_text)


@state_admin_router.message(StateMailing.input_text)
async def mailing_text(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    try:
        data = await state.get_data()
        if data['option'] == 'all':
            users = await get_all_user(session)
        elif data['option'] == 'sub':
            users = await get_all_subscription(session)
        else:
            users = await get_no_subscription(session)
        count_not_suc = 0
        old_progress = 0
        message_wait = await message.answer(
            _('message_mailing_status', lang).format(percent=0)
        )
        if message.photo:
            photo = message.photo[-1]
            caption = message.caption if message.caption else ''
            for idx, user in enumerate(users):
                try:
                    await message.bot.send_photo(
                        user.tgid,
                        photo.file_id,
                        caption=caption,
                        reply_markup=await mailing_button_message(
                            user.lang, data['button']
                        )
                    )
                except Exception as e:
                    log.info('user block bot')
                    count_not_suc += 1
                finally:
                    old_progress = await update_progress(
                        idx, len(users), old_progress, message_wait, lang
                    )
        else:
            for idx, user in enumerate(users):
                try:
                    await message.bot.send_message(
                        user.tgid, message.text,
                        reply_markup=await mailing_button_message(
                            user.lang, data['button']
                        )
                    )
                except Exception as e:
                    log.info('user block bot')
                    count_not_suc += 1
                finally:
                    old_progress = await update_progress(
                        idx, len(users), old_progress, message_wait, lang
                    )
        await message.answer(
            _('result_mailing_text', lang).format(
                all_count=len(users),
                suc_count=len(users) - count_not_suc,
                count_not_suc=count_not_suc
            ),
            reply_markup=await admin_dashboard_keyboard(lang)
        )
    except Exception as e:
        log.error('error mailing', exc_info=e)
        await message.answer(_('error_mailing_text', lang))
    await state.clear()


async def update_progress(idx, total_users, old_progress, message, lang):
    try:
        progress = int(((idx + 1) / total_users) * 100)
        if progress % 10 == 0 and progress != old_progress:
            await message.edit_text(
                text=_('message_mailing_status', lang)
                .format(percent=int(progress))
            )
        return progress
    except Exception as e:
        log.error('error update_progress', exc_info=e)


async def update_client(message, users, lang):
    for user in users:
        try:
            await message.bot.send_message(
                user.tgid, _('main_message', user.lang),
                reply_markup=ReplyKeyboardRemove()
            )
        except Exception as e:
            log.info('user block bot')
            continue
    await message.answer(
        _('bot_update_success', lang)
    )
