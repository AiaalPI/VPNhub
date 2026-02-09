import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message
from aiogram.utils.formatting import Text, Code, Bold
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_promo_code
from bot.database.methods.get import (
    get_all_promo_code,
    get_all_application_referral,
    get_application_referral_check_false
)
from bot.database.methods.insert import add_promo
from bot.database.methods.update import succes_aplication
from bot.keyboards.inline.admin_inline import (
    promocode_menu,
    promocode_delete,
    application_referral_menu, application_success, type_promo_code
)
from bot.keyboards.reply.admin_reply import back_admin_menu, admin_menu
from bot.misc.callbackData import (
    PromocodeDelete,
    AplicationReferral,
    ApplicationSuccess, SelectTypePromoCode
)
from bot.misc.language import Localization, get_lang
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

referral_router = Router()


class NewPromo(StatesGroup):
    input_text_promo = State()
    input_percent_promo = State()
    input_day_promo = State()
    input_count_use_promo = State()


@referral_router.message(F.text.in_(btn_text('admin_promo_btn')))
async def promo_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('control_promo_text', lang),
        reply_markup=await promocode_menu(lang)
    )


@referral_router.message(F.text.in_(btn_text('admin_reff_system_btn')))
async def referral_system_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('who_width_text', lang),
        reply_markup=await application_referral_menu(lang)
    )


@referral_router.callback_query(AplicationReferral.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: AplicationReferral,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.type:
        application_referral = await get_all_application_referral(session)
    else:
        application_referral = await get_application_referral_check_false(
            session
        )
    if len(application_referral) == 0:
        await call.message.answer(_('not_withdrawal', lang))
    for application in application_referral:
        text_application = await show_application_referral(application, lang)
        if application.check_payment:
            await call.message.answer(**text_application.as_kwargs())
        else:
            await call.message.answer(
                **text_application.as_kwargs(),
                reply_markup=await application_success(
                    application.id,
                    call.message.message_id,
                    lang
                )
            )
    await call.answer()


async def show_application_referral(data, lang):
    if data.check_payment:
        check_payment = _('withdrawal_success', lang)
    else:
        check_payment = _('withdrawal_payment_expected', lang)
    return Text(
        _('withdrawal_number_s', lang), data.id, '\n',
        _('withdrawal_amount_s', lang), Code(data.amount), '₽\n',
        _('withdrawal_info_s', lang), data.payment_info, '\n',
        _('withdrawal_user_connect_s', lang), data.communication, '\n',
        _('withdrawal_telegram_id_s', lang), Code(data.user_tgid), '\n',
        _('withdrawal_condition_s', lang), check_payment
    )


@referral_router.callback_query(F.data == 'new_promo')
async def callback_new_promo(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await edit_message(
        call.message,
        text=_('create_new_promo_text', lang)
    )
    await call.message.answer(
        _('input_text_promo_message', lang),
        reply_markup=await back_admin_menu(lang)
    )
    await state.set_state(NewPromo.input_text_promo)
    await call.answer()


@referral_router.message(NewPromo.input_text_promo)
async def input_name(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    try:
        await state.update_data(text_promo=message.text.strip())
        await message.answer(
            _('promo_selected_type_message', lang),
            reply_markup=await type_promo_code(lang)
        )
    except Exception as e:
        await message.answer(
            _('error_not_found', lang),
            reply_markup=await admin_menu(lang)
        )
        log.error('error input name promo', exc_info=e)
        await state.clear()


@referral_router.callback_query(SelectTypePromoCode.filter())
async def input_name(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: SelectTypePromoCode,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.type_promo == 1:
        await call.message.answer(_('input_percent_message', lang))
        await state.set_state(NewPromo.input_percent_promo)
    elif callback_data.type_promo == 2:
        await call.message.answer(_('promo_input_count_day_message', lang))
        await state.set_state(NewPromo.input_day_promo)


@referral_router.message(NewPromo.input_day_promo)
async def input_day_promo_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    try:
        try:
            promo_code_day = int(message.text.strip())
        except Exception as e:
            await message.answer(
                _('error_input_amount_add_balance', lang)
            )
            log.info(e)
            return
        if 0 >= promo_code_day or promo_code_day > 1000:
            await message.answer(_('error_input_day', lang))
            return
        await state.update_data(promo_code_day=promo_code_day)
        await message.answer(_('input_count_use_message', lang))
        await state.set_state(NewPromo.input_count_use_promo)
    except Exception as e:
        await message.answer(
            _('error_new_promo_text', lang),
            reply_markup=await admin_menu(lang)
        )
        log.info(e)


@referral_router.message(NewPromo.input_percent_promo)
async def input_price_promo(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    try:
        try:
            promo_code_percent = int(message.text.strip())
        except Exception as e:
            await message.answer(
                _('error_input_amount_add_balance', lang)
            )
            log.info(e)
            return
        if 0 >= promo_code_percent or promo_code_percent > 99:
            await message.answer(_('error_input_percent', lang))
            return
        await state.update_data(promo_code_percent=promo_code_percent)
        await message.answer(_('input_count_use_message', lang))
        await state.set_state(NewPromo.input_count_use_promo)
    except Exception as e:
        await message.answer(
            _('error_new_promo_text', lang),
            reply_markup=await admin_menu(lang)
        )
        log.info(e)


@referral_router.message(NewPromo.input_count_use_promo)
async def input_time_promo(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    try:
        try:
            promo_code_count_use = int(message.text.strip())
        except Exception as e:
            await message.answer(
                _('error_input_amount_add_balance', lang)
            )
            log.info(e)
            return
        data = await state.get_data()
        percent = data.get('promo_code_percent', 0)
        day = data.get('promo_code_day')
        await add_promo(
            session,
            data['text_promo'],
            percent,
            day,
            promo_code_count_use
        )
        await message.answer(
            _('new_promo_success', lang),
            reply_markup=await admin_menu(lang)
        )
    except Exception as e:
        await message.answer(
            _('error_new_promo_text', lang),
            reply_markup=await admin_menu(lang)
        )
        log.info(e)
    await state.clear()


@referral_router.callback_query(F.data == 'show_promo')
async def callback_show_promo(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    all_promo = await get_all_promo_code(session)
    if len(all_promo) == 0:
        await edit_message(
            call.message,
            text=_('promo_not_list', lang)
        )
        await call.answer()
        return
    await edit_message(
        call.message,
        text=_('promo_list_all', lang)
    )
    for promo in all_promo:
        if promo.type_promo == 1:
            text_server = Text(
                Code(promo.text),
                f' | {promo.percent} %'
                f' - ', Bold(f'{len(promo.person)}/{promo.count_use}'), ' 🏷'
            )
        else:
            text_server = Text(
                Code(promo.text),
                f' | {promo.count_days} day'
                f' - ', Bold(f'{len(promo.person)}/{promo.count_use}'), ' 🏷'
            )
        await call.message.answer(
            **text_server.as_kwargs(),
            reply_markup=await promocode_delete(
                promo.id,
                call.message.message_id,
                lang
            )
        )
    await call.answer()


@referral_router.callback_query(PromocodeDelete.filter())
async def callback_delete_promo(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: PromocodeDelete,
    state: FSMContext,
):
    lang = await get_lang(session, call.from_user.id, state)
    try:
        id_promo = callback_data.id_promo
        await delete_promo_code(session, id_promo)
    except Exception as e:
        await call.message.answer(_('error_promo_delete_text', lang))
        log.error('error delete promo code', exc_info=e)
    try:
        await call.message.edit_text(
            _('promo_delete_text', lang),
        )
    except Exception as e:
        log.error(e, 'error edit message')
    await call.answer()


@referral_router.callback_query(ApplicationSuccess.filter())
async def callback_success_application(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ApplicationSuccess,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    try:
        await succes_aplication(session, callback_data.id_application)
        await call.message.answer(_('application_paid', lang))
    except Exception as e:
        await call.message.answer(_('application_error_save', lang))
        log.error(e, 'error save application')
    try:
        mes_id = callback_data.mes_id
        await call.message.edit_text(
            _('application_success_text', lang),
            inline_message_id=str(mes_id)
        )
    except Exception as e:
        log.error(e, 'error edit message')
    await call.answer()
