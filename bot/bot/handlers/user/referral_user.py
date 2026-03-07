import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.deep_linking import create_start_link
from aiogram.utils.formatting import Text, Italic, Code
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import (
    get_promo_code,
    get_person,
    get_count_referral_user,
    get_referral_balance,
    get_referral_bonus_stats,
    get_first_marzban_server,
    get_key_user,
)
from bot.database.methods.insert import add_withdrawal, add_key
from bot.database.methods.update import (
    add_pomo_code_person,
    reduce_referral_balance_person,
    add_time_key, promo_user_use
)
from bot.handlers.user.edit_or_get_key import choosing_protocol_or_server
from bot.keyboards.inline.user_inline import (
    share_link,
    promo_code_button,
    message_admin_user,
    back_menu_button,
    user_menu,
    connect_vpn_menu,
    choose_type_vpn_help,
    instruction_manual,
    review_claim_keyboard,
    review_admin_moderation_keyboard,
    support_menu,
    support_renew_keyboard,
)
from bot.misc.callbackData import (
    ReferralKeys,
    ChooseTypeVpnHelp,
    ReviewBonusModeration
)
from bot.misc.language import Localization, get_lang
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.util import CONFIG
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

referral_router = Router()

_ = Localization.text


class ActivatePromocode(StatesGroup):
    input_promo = State()


class WithdrawalFunds(StatesGroup):
    input_amount = State()
    payment_method = State()
    communication = State()


class SupportState(StatesGroup):
    input_message_admin = State()


async def get_referral_link(message, user_id):
    return await create_start_link(
        message.bot,
        str(user_id),
        encode=True
    )


@referral_router.callback_query(F.data.in_('promokod_btn'))
async def give_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await edit_message(
        call.message,
        photo='bot/img/fon.jpg',
        caption=_('referral_promo_code', lang),
        reply_markup=await promo_code_button(lang)
    )


# days-only referral tuning (keep in sync with handlers/user/main.py)
NEW_USER_TRIAL_DAYS = 7
REFERRAL_TRIAL_BONUS_DAYS = 5
REFERRER_PAYMENT_BONUS_DAYS = 3
REVIEW_BONUS_DAYS = 14


def _ref_text(
    lang: str,
    link_ref: str,
    invited: int,
    paid_count: int,
    total_days: int
) -> str:
    return _('referral_program_text', lang).format(
        trial_days=NEW_USER_TRIAL_DAYS,
        trial_bonus_days=REFERRAL_TRIAL_BONUS_DAYS,
        cashback_days=REFERRER_PAYMENT_BONUS_DAYS,
        count=invited,
        paid_count=paid_count,
        total_days=total_days,
        link_ref=link_ref,
    )


@referral_router.callback_query(F.data.in_('affiliate_btn'))
async def referral_system_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)

    invited = await get_count_referral_user(session, call.from_user.id)
    paid_count, total_days = await get_referral_bonus_stats(
        session,
        call.from_user.id
    )

    link_ref = await get_referral_link(call.message, call.from_user.id)
    caption = _ref_text(lang, link_ref, invited, paid_count, total_days)

    # IMPORTANT: pass 0 balance to hide "withdrawal" buttons if keyboard has them
    await edit_message(
        call.message,
        photo='bot/img/referral_program.jpg',
        caption=caption,
        reply_markup=await share_link(link_ref, lang, 0)
    )


@referral_router.callback_query(F.data == 'promo_code')
async def successful_payment(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
):
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.answer(
        _('input_promo_user', lang),
        reply_markup=await back_menu_button(lang)
    )
    await call.answer()
    await state.set_state(ActivatePromocode.input_promo)


@referral_router.callback_query(F.data == 'withdrawal_of_funds')
async def withdrawal_of_funds(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.delete()
    await call.message.answer(
        _('input_amount_withdrawal_min', lang)
        .format(minimum_amount=CONFIG.minimum_withdrawal_amount),
        reply_markup=await back_menu_button(lang),
    )
    await call.answer()
    await state.set_state(WithdrawalFunds.input_amount)


@referral_router.message(WithdrawalFunds.input_amount)
async def payment_method(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    amount = message.text.strip()
    try:
        amount = int(amount)
    except Exception as e:
        log.info(e, 'incorrect amount')
    balance = await get_referral_balance(session, message.from_user.id)
    if (
            type(amount) is not int or
            CONFIG.minimum_withdrawal_amount > amount or
            amount > balance
    ):
        await message.answer(
            _('error_incorrect', lang),
            reply_markup=await back_menu_button(lang)
        )
        return
    await state.update_data(amount=amount)
    await message.answer(
        _('where_transfer_funds', lang),
        reply_markup=await back_menu_button(lang)
    )
    await state.set_state(WithdrawalFunds.payment_method)


@referral_router.message(WithdrawalFunds.payment_method)
async def choosing_connect(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(payment_info=message.text.strip())
    await message.answer(
        _('how_i_contact_you', lang),
        reply_markup=await back_menu_button(lang)
    )
    await state.set_state(WithdrawalFunds.communication)


@referral_router.message(WithdrawalFunds.communication)
async def save_payment_method(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    communication = message.text.strip()
    data = await state.get_data()
    payment_info = data['payment_info']
    amount = data['amount']
    try:
        await add_withdrawal(
            session=session,
            amount=amount,
            payment_info=payment_info,
            tgid=message.from_user.id,
            communication=communication
        )
    except Exception as e:
        log.error(e, 'error add withdrawal')
        await message.answer(_('error_send_admin', lang))
        await state.clear()
    if await reduce_referral_balance_person(
            session, amount, message.from_user.id
    ):
        await message.answer(
            _('referral_system_success', lang)
        )
        await message.bot.send_message(
            CONFIG.admin_tg_id,
            _(
                'withdrawal_funds_has_been',
                await get_lang(session, message.from_user.id)
            ).format(amount=amount)
        )
    else:
        await message.answer(
            _('error_withdrawal_funds_not_balance', lang)
        )
    await state.clear()


@referral_router.message(ActivatePromocode.input_promo)
async def promo_check(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    text_promo = message.text.strip()
    promo_code = await get_promo_code(session, text_promo)
    if promo_code is not None:
        try:
            percent = promo_code.percent
            await add_pomo_code_person(
                session,
                message.from_user.id,
                promo_code
            )
            if promo_code.type_promo == 1:
                await message.answer(
                    _('promo_success_percent_user', lang)
                    .format(
                        percent=percent
                    )
                )
            elif promo_code.type_promo == 2:
                await promo_user_use(
                    session,
                    promo_code.id,
                    message.from_user.id
                )
                keys = await get_key_user(session, message.from_user.id)
                await message.answer(
                    _('promo_success_day_user', lang).format(
                        day=promo_code.count_days
                    ),
                    reply_markup=await connect_vpn_menu(
                        lang,
                        keys,
                        'referral_bonus',
                        add_day=promo_code.count_days
                    )
                )
            else:
                raise Exception('Type promo error')
            lang_admin = await get_lang(session, CONFIG.admin_tg_id)
            text = Text(
                _('message_text_user', lang_admin),
                f' {message.from_user.full_name} ',
                Code(message.from_user.id), ' ',
                _('message_text_user_input_promo', lang_admin),
                f' {text_promo}'
            )
            await message.bot.send_message(
                CONFIG.admin_tg_id,
                **text.as_kwargs()
            )
            await message.answer_photo(
                photo=FSInputFile('bot/img/main_menu.jpg'),
                reply_markup=await user_menu(lang, message.from_user.id)
            )
        except Exception as e:
            await message.answer(
                _('uses_promo_user', lang)
            )
    else:
        await message.answer(
            _('referral_promo_code_none', lang)
        )
    await state.clear()


@referral_router.callback_query(F.data == 'message_admin')
async def message_admin(
    callback_query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, callback_query.from_user.id, state)
    await callback_query.message.answer(
        _('input_message_user_admin', lang),
        reply_markup=await back_menu_button(lang),
        disable_web_page_preview=True
    )
    await state.set_state(SupportState.input_message_admin)
    await callback_query.answer()


@referral_router.callback_query(ChooseTypeVpnHelp.filter())
async def choose_type_vpn_help_callback(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChooseTypeVpnHelp,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    text = (
        'Инструкции по подключению'
        if lang == 'ru'
        else 'Connection instructions'
    )
    await edit_message(
        call.message,
        photo='bot/img/help.jpg',
        caption=text,
        reply_markup=await instruction_manual(lang, callback_data.type_vpn),
    )
    await call.answer()


@referral_router.callback_query(F.data.in_('help_btn'))
async def info_message_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await edit_message(
        call.message,
        photo='bot/img/help.jpg',
        caption=_('input_message_user_admin', lang),
        reply_markup=await support_menu(lang),
    )
    await call.answer()


def _format_support_date(subscription_ts: int | None, lang: str) -> str:
    if subscription_ts is None:
        return _('support_date_unknown', lang)
    dt = datetime.fromtimestamp(subscription_ts)
    if (lang or '').lower().startswith('ru'):
        return dt.strftime('%d.%m.%Y')
    return dt.strftime('%Y-%m-%d')


def _tokyo_node_online(nodes: list[dict]) -> bool | None:
    tokyo_node = None
    for node in nodes:
        name = str(node.get('name', '')).strip().lower()
        if name == 'tokyo-node-1':
            tokyo_node = node
            break
    if tokyo_node is None:
        return None
    if tokyo_node.get('is_connected') is True or tokyo_node.get('connected') is True:
        return True
    values = {
        str(value).strip().lower()
        for value in (
            tokyo_node.get('status'),
            tokyo_node.get('state'),
            tokyo_node.get('health'),
            tokyo_node.get('connection_status'),
        )
        if value is not None and str(value).strip()
    }
    if values.intersection({'connected', 'online', 'healthy', 'up', 'active'}):
        return True
    if values.intersection({'disconnected', 'offline', 'down', 'inactive', 'error'}):
        return False
    return None


async def _get_tokyo_node_status(session: AsyncSession, best_key) -> bool | None:
    server = None
    if (
        best_key is not None
        and getattr(best_key, 'server_table', None) is not None
        and int(getattr(best_key.server_table, 'type_vpn', -1)) == CONFIG.TypeVpn.MARZBAN.value
    ):
        server = best_key.server_table
    if server is None:
        server = await get_first_marzban_server(session)
    if server is None:
        return None
    try:
        manager = ServerManager(server, timeout=10)
        await manager.login()
        nodes = await manager.get_nodes()
        if nodes is None:
            return None
        return _tokyo_node_online(nodes)
    except Exception:
        log.exception('event=support_auto_check status=marzban_failed user_server_id=%s', getattr(server, 'id', None))
        return None


@referral_router.callback_query(F.data == 'support_auto_check')
async def support_auto_check(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    keys = await get_key_user(session, call.from_user.id)
    now_ts = int(datetime.now().timestamp())
    best_key = None
    if keys:
        best_key = max(keys, key=lambda key: int(key.subscription or 0))
    expires_ts = int(best_key.subscription or 0) if best_key is not None else None
    expires_at = _format_support_date(expires_ts, lang)
    has_active_sub = bool(best_key is not None and int(best_key.subscription or 0) > now_ts)
    server_online = await _get_tokyo_node_status(session, best_key)

    if not has_active_sub:
        await edit_message(
            call.message,
            photo='bot/img/help.jpg',
            caption=_('support_diag_sub_problem', lang).format(date=expires_at),
            reply_markup=await support_renew_keyboard(lang),
        )
        await call.answer()
        return

    if server_online is not True:
        await edit_message(
            call.message,
            photo='bot/img/help.jpg',
            caption=_('support_diag_server_problem', lang).format(date=expires_at),
            reply_markup=await support_menu(lang),
        )
        await call.answer()
        return

    await edit_message(
        call.message,
        photo='bot/img/help.jpg',
        caption=_('support_diag_all_good', lang).format(date=expires_at),
        reply_markup=await support_menu(lang),
    )
    await call.answer()


@referral_router.callback_query(F.data == 'review_btn')
async def review_bonus_screen(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    person = await get_person(session, call.from_user.id)
    if person is None:
        await call.answer()
        return
    if person.review_bonus_used:
        await call.answer(_('review_bonus_already_used', lang), show_alert=True)
        return
    await edit_message(
        call.message,
        photo='bot/img/help.jpg',
        caption=_('review_bonus_intro', lang),
        reply_markup=await review_claim_keyboard(lang)
    )
    await call.answer()


@referral_router.callback_query(F.data == 'review_claim_btn')
async def review_bonus_claim(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    person = await get_person(session, call.from_user.id)
    if person is None:
        await call.answer()
        return
    if person.review_bonus_used:
        await call.answer(_('review_bonus_already_used', lang), show_alert=True)
        return

    admin_lang = await get_lang(session, CONFIG.admin_tg_id)
    await call.message.bot.send_message(
        CONFIG.admin_tg_id,
        _('review_bonus_admin_request', admin_lang).format(
            name=person.fullname or person.username or str(person.tgid),
            user_id=person.tgid
        ),
        reply_markup=await review_admin_moderation_keyboard(
            admin_lang, person.tgid
        )
    )
    await call.answer(_('review_bonus_request_sent', lang), show_alert=True)
    await call.message.answer(_('review_bonus_waiting_admin', lang))


@referral_router.callback_query(ReviewBonusModeration.filter())
async def review_bonus_moderation(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ReviewBonusModeration,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    if not CONFIG.is_admin(call.from_user.id):
        await call.answer(_('error_send_admin', lang), show_alert=True)
        return
    user = await get_person(session, callback_data.user_id)
    if user is None:
        await call.answer(_('not_message_user', lang), show_alert=True)
        return
    user_lang = await get_lang(session, user.tgid)
    if callback_data.action == 'approve':
        if user.review_bonus_used:
            await call.answer(_('review_bonus_already_used', lang), show_alert=True)
            return
        keys = await get_key_user(session, user.tgid)
        bonus_seconds = REVIEW_BONUS_DAYS * 24 * 60 * 60
        if keys:
            best_key = max(keys, key=lambda key: int(key.subscription or 0))
            await add_time_key(session, best_key.id, bonus_seconds, id_payment='review_bonus')
        else:
            await add_key(
                session,
                user.tgid,
                bonus_seconds,
                id_payment='review_bonus'
            )
        user.review_bonus_used = True
        await session.commit()
        await call.message.bot.send_message(
            user.tgid,
            _('review_bonus_user_success', user_lang).format(
                days=REVIEW_BONUS_DAYS
            )
        )
        await call.message.edit_text(
            _('review_bonus_admin_approved', lang).format(
                name=user.fullname or user.username or str(user.tgid),
                user_id=user.tgid
            )
        )
        await call.answer(_('application_paid', lang))
        return

    await call.message.bot.send_message(
        user.tgid,
        _('review_bonus_user_rejected', user_lang)
    )
    await call.message.edit_text(
        _('review_bonus_admin_rejected', lang).format(
            name=user.fullname or user.username or str(user.tgid),
            user_id=user.tgid
        )
    )
    await call.answer(_('cancel_admin', lang))


@referral_router.message(SupportState.input_message_admin)
async def input_message_admin(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    person = await get_person(session, message.from_user.id)
    try:
        text = Text(
            _('message_user_admin', lang)
            .format(
                fullname=person.fullname,
                username=person.username,
                telegram_id=person.tgid
            ),
            Italic(message.text.strip())
        )
        await message.bot.send_message(
            CONFIG.admin_tg_id, **text.as_kwargs(),
            reply_markup=await message_admin_user(person.tgid, lang)
        )
        await message.answer(
            _('message_user_admin_success', lang)
        )
    except Exception as e:
        await message.answer(
            _('error_message_user_admin_success', lang)
        )
        log.error(e, 'Error admin message')
    await state.clear()


@referral_router.callback_query(ReferralKeys.filter())
async def message_admin(
    callback_query: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    callback_data: ReferralKeys,
    state: FSMContext
):
    lang = await get_lang(session, callback_query.from_user.id, state)
    key_id = callback_data.key_id
    if key_id == 0:
        key = await add_key(
            session,
            callback_query.from_user.id,
            callback_data.add_day * 86400
        )
        await callback_query.message.delete()
        await choosing_protocol_or_server(
            callback_query,
            session,
            js,
            remove_key_subject,
            state,
            callback_query.from_user.id,
            lang,
            back_data='back_general_menu_btn',
            key_id=key.id,
        )
        await callback_query.answer()
        return
    await add_time_key(session, key_id, callback_data.add_day * 86400)
    await edit_message(
        callback_query.message,
        text=_('referral_new_user_success', lang)
    )
