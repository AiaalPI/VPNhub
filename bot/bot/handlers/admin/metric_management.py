import logging

from aiogram import Router, F, html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery,
)
from aiogram.utils.deep_linking import create_start_link
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.delete import delete_metric_id
from bot.database.methods.get import (
    get_all_metric,
    get_metric,
    get_users_trial_metric,
    get_users_payments_metric,
    get_users_payments_tariff_metric,
    get_paying_users_count, get_metric_stats
)
from bot.database.methods.insert import create_metric
from bot.keyboards.inline.admin_inline import metric_menu, metric_remove_back
from bot.misc.callbackData import ShowMetric, RemoveMetric
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG
from bot.service.edit_message import edit_message
from bot.service.excel_service import get_excel_file

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

FORMAT_DATA = "%d.%m.%Y %H:%M"
ONE_HOUSE = 3600
DEFAULT_UTC = CONFIG.UTC_time * ONE_HOUSE

metric_management_router = Router()


class CreateMetric(StatesGroup):
    input_name = State()


@metric_management_router.message(
    (F.text.in_(btn_text('admin_metric_list_btn')))
)
async def message_show_list_metrics(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    all_metric = await get_all_metric(session)
    paginator = await metric_menu(
        metric_management_router,
        lang,
        all_metric
    )
    await message.answer(
        _('metric_list_message', lang),
        reply_markup=paginator.as_markup()
    )


@metric_management_router.callback_query(F.data == 'show_all_metrics')
async def callback_show_list_metrics(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    all_metric = await get_all_metric(session)
    paginator = await metric_menu(
        metric_management_router,
        lang,
        all_metric
    )
    await edit_message(
        call.message,
        text=_('metric_list_message', lang),
        reply_markup=paginator.as_markup()
    )


@metric_management_router.callback_query(ShowMetric.filter())
async def callback_show_metric(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ShowMetric
):
    lang = await get_lang(session, call.from_user.id, state)
    metric = await get_metric(session, callback_data.id_metric)
    link = await create_start_link(
        call.message.bot,
        metric.code,
        encode=False
    )
    users_use_trial_period = await get_users_trial_metric(session, metric.id)
    payments = await get_users_payments_metric(session, metric.id)
    payments_tariff = await get_users_payments_tariff_metric(
        session, metric.id
    )
    all_sum = 0.0
    for payment in payments:
        all_sum += payment.amount
    payment_tariff_str = ''
    for tariff in payments_tariff:
        payment_tariff_str += (
            str(tariff['amount']) + ' ₽ - '
            + str(tariff['user_count']) + ' 💳'
            + '\n'
        )
    count_user_payment = await get_paying_users_count(session, metric.id)
    await edit_message(
        call.message,
        text=_('metric_show',lang).format(
            name=html.quote(metric.text),
            link=link,
            count_users=len(metric.users),
            count_trial_users=len(users_use_trial_period),
            count_user_payment=count_user_payment,
            sum_payment=str(all_sum) + ' ₽',
            payments_tariff=payment_tariff_str
        ),
        reply_markup=await metric_remove_back(lang, metric.id)
    )


@metric_management_router.callback_query(F.data == 'add_metric')
async def add_metric_input_name(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await edit_message(
        call.message,
        text=_('metric_add_name', lang)
    )
    await state.set_state(CreateMetric.input_name)


@metric_management_router.message(CreateMetric.input_name)
async def add_metric_create(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    await create_metric(session, html.quote(message.text))
    await state.clear()
    await message_show_list_metrics(message, session, state)


@metric_management_router.callback_query(RemoveMetric.filter())
async def remove_metric(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: RemoveMetric
):
    await delete_metric_id(session, callback_data.id_metric)
    await callback_show_list_metrics(call, session, state)


@metric_management_router.callback_query(F.data == 'statistic_metric')
async def callback_show_list_metrics(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    results = await get_metric_stats(session)
    list_metrics = []
    column_payments = [
        _('metric_name', lang),
        _('metric_link', lang),
        _('metric_count_user', lang),
        _('metric_count_trial_user', lang),
        _('metric_count_end_trial_user', lang),
        _('metric_count_user_payment', lang),
        _('metric_count_user_payment_not_sub', lang)
    ]
    for result in results:
        link = await create_start_link(
            call.message.bot,
            result.get('code'),
            encode=False
        )
        list_metrics.append(
            [
                result.get('text'),
                link,
                result.get('users_count'),
                result.get('trial_started'),
                result.get('trial_ended'),
                result.get('subscribed'),
                result.get('subscription_ended'),
            ]
        )
    if len(list_metrics) == 0:
        return
    file = await get_excel_file(
        column_payments,
        list_metrics,
        'Metric statistics'
    )
    try:
        await call.message.answer_document(
            file,
            caption=_('list_of_metric_file', lang)
        )
    except Exception as e:
        await call.message.answer(_('error_list_of_metric_file', lang))
        log.error(e, 'error send file metrics.excel')
