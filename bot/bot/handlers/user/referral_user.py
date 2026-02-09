import logging

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
    get_referral_balance, get_key_user,
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
    user_menu, connect_vpn_menu
)
from bot.misc.callbackData import ReferralKeys
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

referral_router = Router()

_ = Localization.text
btn_text = Localization.get_reply_button


class ActivatePromocode(StatesGroup):
    input_promo = State()


class WithdrawalFunds(StatesGroup):
    input_amount = State()
    payment_method = State()
    communication = State()
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


@referral_router.callback_query(F.data.in_(btn_text('promokod_btn')))
async def give_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/fon.jpg'),
        caption=_('referral_promo_code', lang),
        reply_markup=await promo_code_button(lang)
    )


@referral_router.callback_query(F.data.in_('affiliate_btn'))
async def referral_system_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    user = await get_person(session, call.from_user.id)
    count_referral_user = await get_count_referral_user(
        session,
        call.from_user.id
    )
    balance = await get_referral_balance(session, call.from_user.id)
    link_ref = await get_referral_link(call.message, call.from_user.id)
    if user.status is not None and user.status == 1:
        percent = user.referral_percent
    else:
        percent = CONFIG.referral_percent
    await edit_message(
        call.message,
        photo='bot/img/referral_program.jpg',
        caption=_('affiliate_reff_text_new', lang).format(
            percent=percent,
            ref_link=link_ref,
            count_referral_user=count_referral_user,
            balance=balance
        ),
        reply_markup=await share_link(link_ref, lang, balance)
    )


@referral_router.callback_query(F.data.in_(btn_text('affiliate_btn')))
async def referral_system_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    user = await get_person(session, call.from_user.id)
    count_referral_user = await get_count_referral_user(
        session,
        call.from_user.id
    )
    balance = await get_referral_balance(session, call.from_user.id)
    link_ref = await get_referral_link(call.message, call.from_user.id)
    if user.status is not None and user.status == 1:
        percent = user.referral_percent
    else:
        percent = CONFIG.referral_percent
    message_text = (
        _('affiliate_reff_text_new', lang)
        .format(
            percent=percent,
            ref_link=link_ref,
            count_referral_user=count_referral_user,
            balance=balance
        )
    )
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/referral_program.jpg'),
        caption=message_text,
        reply_markup=await share_link(link_ref, lang, balance)
    )


@referral_router.callback_query(F.data == 'promo_code')
async def successful_payment(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
):
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.answer(
        _('input_promo_user', lang)
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
        await message.answer(_('error_incorrect', lang))
        return
    await state.update_data(amount=amount)
    await message.answer(_('where_transfer_funds', lang))
    await state.set_state(WithdrawalFunds.payment_method)


@referral_router.message(WithdrawalFunds.payment_method)
async def choosing_connect(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    await state.update_data(payment_info=message.text.strip())
    await message.answer(_('how_i_contact_you', lang))
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
        disable_web_page_preview=True
    )
    await state.set_state(WithdrawalFunds.input_message_admin)
    await callback_query.answer()


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
        reply_markup=await back_menu_button(lang),
    )
    await state.set_state(WithdrawalFunds.input_message_admin)


@referral_router.callback_query(F.data.in_(btn_text('help_btn')))
async def info_message_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/help.jpg'),
        caption=_('input_message_user_admin', lang),
        reply_markup=await back_menu_button(lang),
        disable_web_page_preview=True
    )
    await state.set_state(WithdrawalFunds.input_message_admin)


@referral_router.message(WithdrawalFunds.input_message_admin)
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
