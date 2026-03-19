import logging
import time

from aiogram import F
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.utils.formatting import Text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.update import promo_user_use, update_auto_pay
from bot.misc.Payment.CryptoBot import CryptoBot
from bot.misc.Payment.Cryptomus import Cryptomus, Heleket
from bot.misc.Payment.KassaSmart import KassaSmart
from bot.misc.Payment.Lava import Lava
from bot.misc.Payment.Stars import Stars, stars_router
from bot.misc.Payment.Wawa import Wawa, WawaSpb, WawaVisa
from bot.misc.Payment.YooMoney import YooMoney
from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.misc.callbackData import (
    ChoosingMonths,
    ChoosingPyment,
    ChoosingPrise,
    DonatePrice,
    PromoCodeChoosing,
    AutoPay,
    YooMoneyManualModeration,
)

from bot.keyboards.inline.user_inline import (
    price_menu,
    replenishment,
    donate_menu,
    back_donate_menu,
    choosing_promo_code,
    back_menu_button,
)
from bot.database.methods.get import (
    get_all_donate,
    get_promo_codes_user
)
from bot.services.message_render_service import edit_message
from bot.webhooks.util import get_message

log = logging.getLogger(__name__)

_ = Localization.text

callback_user = Router()
callback_user.include_router(stars_router)
CONVERT_PANY_RUBLS = 100

types_of_payments = {
    'KassaSmart': KassaSmart,
    'YooMoney': YooMoney,
    'Lava': Lava,
    'Cryptomus': Cryptomus,
    'CryptoBot': CryptoBot,
    'Stars': Stars,
    'Wawa': Wawa,
    'WawaSpb': WawaSpb,
    'WawaVisa': WawaVisa,
    'Heleket': Heleket,
}


class Email(StatesGroup):
    input_email = State()


class Price(StatesGroup):
    input_price = State()


@callback_user.callback_query(AutoPay.filter())
async def callback_price(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: AutoPay,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await update_auto_pay(session, callback_data.work, call.from_user.id)
    if callback_data.work:
        text = _('work_auto_pay_message', lang)
    else:
        text = _('not_work_auto_pay_message', lang)
    await call.message.answer(text=text)
    await call.answer()


@callback_user.callback_query(ChoosingMonths.filter())
async def my_callback_foo(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChoosingMonths,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    promo_code = await get_promo_codes_user(session, call.from_user.id)
    if (
        len(promo_code) != 0
        and (
            callback_data.type_pay == CONFIG.type_payment.get(0)
            or callback_data.type_pay == CONFIG.type_payment.get(1)
        )
    ):
        await edit_message(
            call.message,
            caption=_('want_use_promocode', lang),
            reply_markup=await choosing_promo_code(
                lang,
                promo_code,
                callback_data.price,
                callback_data.type_pay,
                key_id=callback_data.key_id,
                id_prot=callback_data.id_prot,
                id_loc=callback_data.id_loc,
                month_count=callback_data.month_count
            )
        )
    else:
        await edit_message(
            call.message,
            caption=_('method_replenishment', lang),
            reply_markup=await replenishment(
                CONFIG,
                callback_data.price,
                lang,
                callback_data.type_pay,
                key_id=callback_data.key_id,
                id_prot=callback_data.id_prot,
                id_loc=callback_data.id_loc,
                month_count=callback_data.month_count,
            )
        )
        text = Text(
            _('admin_message_choosing_month', CONFIG.languages)
            .format(
                username=call.from_user.username,
                user_id=call.from_user.id,
                month_count=callback_data.month_count
            )
        )
        await call.message.bot.send_message(
            CONFIG.admin_tg_id,
            **text.as_kwargs()
        )
    await call.answer()


@callback_user.callback_query(PromoCodeChoosing.filter())
async def callback_price(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: PromoCodeChoosing,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.percent != 0:
        price = callback_data.price
        percent = callback_data.percent
        price = price - int(price * (percent * 0.01))
        await promo_user_use(session, callback_data.id_promo, call.from_user.id)
        text = _('method_replenishment_promo', lang).format(
            percent=percent
        )
    else:
        price = callback_data.price
        text = _('method_replenishment', lang)
    await edit_message(
        call.message,
        caption=text,
        reply_markup=await replenishment(
            CONFIG,
            price,
            lang,
            callback_data.type_pay,
            key_id=callback_data.key_id,
            id_prot=callback_data.id_prot,
            id_loc=callback_data.id_loc,
            month_count=callback_data.month_count
        )
    )
    await call.answer()


@callback_user.callback_query(ChoosingPyment.filter())
async def callback_price(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChoosingPyment,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.edit_text(
        _('choosing_amount_menu', lang),
        call.inline_message_id,
        reply_markup=await price_menu(CONFIG, callback_data.payment))
    await call.answer()


@callback_user.callback_query(ChoosingPrise.filter())
async def callback_payment(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: ChoosingPrise,
    state: FSMContext
):
    await state.clear()
    try:
        # Acknowledge callback immediately to avoid client-side spinner timeout
        await call.answer()
    except Exception:
        log.debug("failed to answer callback in callback_payment", exc_info=True)
    type_pay = callback_data.type_pay
    key_id = callback_data.key_id
    if types_of_payments.get(callback_data.payment):
        await pay_payment(
            session,
            callback_data.payment,
            call.message,
            call.from_user,
            callback_data.price,
            callback_data.month_count,
            call.data,
            type_pay,
            key_id,
            id_prot=callback_data.id_prot,
            id_loc=callback_data.id_loc
        )
    else:
        raise NameError(callback_data.payment)


async def pay_payment(
    session: AsyncSession,
    payment, message,
    from_user, price,
    month_count, data,
    type_pay, key_id,
    id_prot, id_loc
):
    if (
            month_count is None
            and (
            type_pay == CONFIG.type_payment.get(0)
            or type_pay == CONFIG.type_payment.get(1)
    )
    ):
        lang = await get_lang(session, message.from_user.id)
        await message.answer(_('error_month_count', lang))
        return
    payment = types_of_payments[payment](
        session,
        CONFIG,
        message,
        from_user.id,
        price,
        month_count,
        type_pay,
        key_id,
        id_prot,
        id_loc,
        data
    )
    await payment.to_pay()


@callback_user.callback_query(YooMoneyManualModeration.filter())
async def yoomoney_manual_moderation(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: YooMoneyManualModeration,
    state: FSMContext,
):
    lang = await get_lang(session, call.from_user.id, state)
    if not CONFIG.is_admin(call.from_user.id):
        await call.answer(_('error_send_admin', lang), show_alert=True)
        return

    user_id = callback_data.user_id
    user_lang = await get_lang(session, user_id)
    type_pay = CONFIG.type_payment.get(
        callback_data.type_pay, CONFIG.type_payment.get(0)
    )

    if callback_data.action == 'approve':
        message = await get_message(call.bot, user_id, 1)
        payment_system = PaymentSystem(
            session=session,
            message=message,
            user_id=user_id,
            donate=type_pay,
            price=callback_data.price,
            month_count=callback_data.month_count,
            id_prot=callback_data.id_prot,
            id_loc=callback_data.id_loc,
            key_id=callback_data.key_id,
        )
        manual_id = (
            f"yoomoney_manual_{user_id}_{callback_data.key_id}_{int(time.time())}"
        )
        await payment_system.successful_payment(
            callback_data.price,
            'YooMoney (manual)',
            id_payment=manual_id,
        )
        await call.message.edit_text(
            f"✅ YooMoney payment confirmed manually\n"
            f"User ID: {user_id}\n"
            f"Amount: {callback_data.price}"
        )
        await call.answer(_('application_paid', lang))
        return

    await call.message.edit_text(
        f"❌ YooMoney payment rejected\n"
        f"User ID: {user_id}\n"
        f"Amount: {callback_data.price}"
    )
    await call.bot.send_message(user_id, _('error_send_admin', user_lang))
    await call.answer(_('cancel_admin', lang))


@callback_user.callback_query(F.data == 'back_donate_menu')
async def callback_payment(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await edit_message(
        call.message,
        caption=_('donate_message', lang)
        .format(fullname=call.from_user.full_name),
        reply_markup=await donate_menu(lang)
    )


@callback_user.callback_query(DonatePrice.filter())
async def callback_payment(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: DonatePrice,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.price == 0:
        await edit_message(
            call.message,
            caption=_('donate_input_price_text', lang),
            reply_markup=await back_menu_button(lang)
        )
        await state.set_state(Price.input_price)
        return
    await edit_message(
        call.message,
        caption=_('method_replenishment', lang),
        reply_markup=await replenishment(
            CONFIG,
            callback_data.price,
            lang,
            CONFIG.type_payment.get(2)
        )
    )


@callback_user.message(Price.input_price)
async def input_price(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    price = message.text.strip()
    if not price.isdigit():
        await message.answer(
            _('donate_input_price_text_not_num', lang),
            reply_markup=await back_menu_button(lang)
        )
        return
    price = int(price)
    if price < 50 or price > 20000:
        await message.answer(
            _('donate_input_price_text_limit', lang),
            reply_markup=await back_menu_button(lang)
        )
        return
    await state.clear()
    await message.answer_photo(
        photo=FSInputFile('bot/img/donate.jpg'),
        caption=_('method_replenishment', lang),
        reply_markup=await replenishment(
            CONFIG,
            price,
            lang,
            CONFIG.type_payment.get(2)
        )
    )


@callback_user.callback_query(F.data == 'donate_list')
async def callback_payment(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    all_donate = await get_all_donate(session)
    list_donate = ''
    for donate in all_donate:
        list_donate += f'{donate.username} - <b>{donate.price} ₽</b>\n'
    await edit_message(
        call.message,
        caption=_('donate_list_users', lang).format(users=list_donate),
        reply_markup=await back_donate_menu(lang)
    )
