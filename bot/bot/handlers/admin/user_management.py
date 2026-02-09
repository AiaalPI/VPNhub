import logging
from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    Message,
    CallbackQuery
)
from aiogram.utils.formatting import Text, Bold
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import (
    get_all_user,
    get_all_subscription,
    get_payments,
    get_person,
    get_key_user, get_name_location_server, get_ref_bord
)
from bot.database.methods.update import (
    add_time_person,
    person_banned_true,
    block_state_person, status_state_person
)
from bot.keyboards.reply.admin_reply import (
    admin_user_menu,
    send_user_button,
    show_user_menu,
    static_user_menu
)
from bot.keyboards.inline.admin_inline import (
    edit_client_menu,
    delete_time_client,
    keys_control
)
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.callbackData import (
    EditUserPanel,
    DeleteTimeClient,
    MessageAdminUser,
    EditKeysUser,
    BlockedUserPanel, StatusUserPanel
)
from bot.misc.language import Localization, get_lang
from bot.misc.loop import delete_key
from bot.misc.util import CONFIG
from bot.service.excel_service import get_excel_file

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

FORMAT_DATA = "%d.%m.%Y %H:%M"
ONE_HOUSE = 3600
DEFAULT_UTC = CONFIG.UTC_time * ONE_HOUSE

user_management_router = Router()


class EditUser(StatesGroup):
    show_user = State()
    add_time = State()
    delete_time = State()
    input_message_user = State()
    input_balance_user = State()
    input_percent_user = State()


@user_management_router.message(
    (F.text.in_(btn_text('admin_users_btn')))
    | (F.text.in_(btn_text('admin_back_users_menu_btn')))
)
async def command(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('admin_user_manager_m', lang),
        reply_markup=await admin_user_menu(lang)
    )


@user_management_router.message(
    F.text.in_(btn_text('admin_show_statistic_btn'))
)
async def control_user_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('admin_user_manager_m', lang),
        reply_markup=await show_user_menu(lang)
    )


@user_management_router.message(
    F.text.in_(btn_text('admin_statistic_show_all_users_btn'))
)
async def show_user_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    all_users = await get_all_user(session)
    list_users = []
    count = 1
    for user in all_users:
        list_users.append(await list_user(user, count))
        count += 1
    if len(list_users) == 0:
        await message.answer(_('error_list_of_all_users_file', lang))
        return
    file = await get_excel_file(
        await list_columns_user(lang),
        list_users,
        'All Users'
    )
    try:
        await message.answer_document(
            file,
            caption=_('list_of_all_users_file', lang)
        )
    except Exception as e:
        await message.answer(_('error_list_of_all_users_file', lang))
        log.error('error send file All Users', exc_info=e)


@user_management_router.message(
    F.text.in_(btn_text('admin_statistic_ref_bord_btn'))
)
async def show_user_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    results = await get_ref_bord(session)
    list_user = []
    column_user = [
        _('ref_name', lang),
        _('ref_username', lang),
        _('ref_count_user', lang),
        _('ref_count_trial_user', lang),
        _('ref_count_end_trial_user', lang),
        _('ref_count_user_payment', lang),
        _('ref_count_user_payment_not_sub', lang)
    ]
    for result in results:
        list_user.append(
            [
                result.get('id'),
                result.get('username'),
                result.get('users_count'),
                result.get('trial_started'),
                result.get('trial_ended'),
                result.get('subscribed'),
                result.get('subscription_ended'),
            ]
        )
    if len(list_user) == 0:
        await message.answer(_('list_of_none_ref_board_file', lang))
        return
    file = await get_excel_file(
        column_user,
        list_user,
        'Ref Lib Bord'
    )
    try:
        await message.answer_document(
            file,
            caption=_('list_of_ref_bord_file', lang)
        )
    except Exception as e:
        await message.answer(_('error_list_of_ref_bord_file', lang))
        log.error(e, 'error send file refbord.excel')


@user_management_router.message(
    F.text.in_(btn_text('admin_statistic_show_sub_users_btn'))
)
async def show_user_sub_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    sub_users = await get_all_subscription(session)
    list_users = []
    count = 1
    keys_user = []
    for user in sub_users:
        for key in user.keys:
            if not key.free_key and not key.trial_period:
                keys_user.append(key)
        user.keys = keys_user
        keys_user = []
        if len(user.keys) == 0:
            continue
        list_users.append(await list_user(user, count))
        count += 1
    if len(list_users) == 0:
        await message.answer(_('none_list_of_sub_users_file', lang))
        return
    file = await get_excel_file(
        await list_columns_user(lang),
        list_users,
        'Subscribe Users'
    )
    try:
        await message.answer_document(
            file,
            caption=_('list_of_sub_users_file', lang)
        )
    except Exception as e:
        await message.answer(_('error_list_of_sub_users_file', lang))
        log.error('error send file subscription_user.txt', exc_info=e)


@user_management_router.message(
    F.text.in_(btn_text('admin_statistic_show_payments_btn'))
)
async def show_statistic_payment(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    payments = await get_payments(session)
    list_payments = []
    count = 1
    column_payments = [
        '№',
        _('user_username', lang),
        _('user_tgid', lang),
        _('payment_system', lang),
        _('payment_amount', lang),
        _('payment_date', lang)
    ]
    for payment in payments:
        list_payments.append(
            [count,
             payment.user,
             payment.payment_id.tgid,
             payment.payment_system,
             payment.amount,
             payment.data.strftime('%d.%m.%Y %H:%M:%S')]
        )
        count += 1
    if len(list_payments) == 0:
        await message.answer(_('none_list_of_payments_file', lang))
        return
    file = await get_excel_file(
        column_payments,
        list_payments,
        'Payments'
    )
    try:
        await message.answer_document(
            file,
            caption=_('list_of_payments_file', lang)
        )
    except Exception as e:
        await message.answer(_('error_list_of_payments_file', lang))
        log.error(e, 'error send file payments.txt')


@user_management_router.message(
    F.text.in_(btn_text('admin_edit_user_btn'))
)
async def edit_user_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('input_telegram_id_user_m', lang),
        reply_markup=await send_user_button(lang)
    )
    await state.set_state(EditUser.show_user)


@user_management_router.message(
    (F.text.in_(btn_text('admin_users_cancellation')))
    | (F.text.in_(btn_text('admin_exit_btn')))
)
async def back_user_control(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await state.clear()
    await message.answer(
        _('admin_user_manager_m', lang),
        reply_markup=await admin_user_menu(lang)
    )


@user_management_router.message(EditUser.show_user)
async def show_user_state(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    try:
        if message.text is None:
            user_id = message.user_shared.user_id
        else:
            user_id = int(message.text.strip())
        client = await get_person(session, int(user_id))
        if client.status is not None and client.status == 1:
            status = _('card_client_admin_status_partner', lang)
            status_ex = True
            if client.referral_percent is not None:
                percent = client.referral_percent
            else:
                percent = CONFIG.referral_percent
        else:
            status = _('card_client_admin_status_default', lang)
            status_ex = False
            percent = CONFIG.referral_percent
        content = Text(
            _('card_client_admin_m', lang).format(
                fullname=client.fullname,
                username=client.username,
                telegram_id=client.tgid,
                status=status,
                ref_percent=percent,
                lang_code=client.lang_tg or '❌',
                referral_balance=client.referral_balance,
                keys=len(client.keys),
                group=client.group if client.group is not None else '❌',
            ),
        )
        await message.answer(
            **content.as_kwargs(),
            reply_markup=await edit_client_menu(
                client.tgid, lang, client.blocked, status_ex)
        )
        await state.update_data(client=client)

    except Exception as e:
        log.info(e, 'client not found')
        await message.answer(
            _('card_client_admin_m_client_none', lang),
            reply_markup=await admin_user_menu(lang)
        )
        await state.clear()


@user_management_router.callback_query(BlockedUserPanel.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: BlockedUserPanel
):
    lang = await get_lang(session, call.from_user.id, state)
    state_blocked = not callback_data.action == 'unblocked'
    block_state = state_blocked
    await block_state_person(session, callback_data.id_user, block_state)
    if state_blocked:
        await call.message.answer(
            _('edit_client_unblocked_message', lang)
        )
    else:
        await call.message.answer(
            _('edit_client_blocked_message', lang)
        )
    await call.answer()


@user_management_router.callback_query(StatusUserPanel.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: StatusUserPanel
):
    lang = await get_lang(session, call.from_user.id, state)
    if not callback_data.status:
        await state.set_state(EditUser.input_percent_user)
        await call.message.answer(
            _('edit_client_input_percent_message', lang)
        )
        await state.update_data(id_user=callback_data.id_user)
        return
    await status_state_person(
        session,
        callback_data.id_user,
        not callback_data.status,
        CONFIG.referral_percent
    )
    await call.message.answer(
        _('edit_client_status_default_message', lang)
    )
    await call.answer()


@user_management_router.message(EditUser.input_percent_user)
async def edit_user_callback_query(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    try:
        try:
            percent = int(message.text.strip())
        except Exception as e:
            await message.answer(
                _('error_input_amount_add_balance', lang)
            )
            log.info(e)
            return
        if 0 >= percent or percent > 100:
            await message.answer(_('error_input_percent', lang))
            return
        data = await state.get_data()
        await state.clear()
        await status_state_person(
            session,
            data.get('id_user'),
            True,
            percent
        )
        await message.answer(
            _('edit_client_status_partner_message', lang)
        )
    except Exception as e:
        log.info(e)


@user_management_router.callback_query(EditUserPanel.filter())
async def callback_work_server(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: EditUserPanel,
    state: FSMContext,
):
    lang = await get_lang(session, call.from_user.id, state)
    if callback_data.action == 'count_use':
        await call.message.answer(
            _('input_count_day_add_time_m', lang)
        )
        await state.set_state(EditUser.add_time)
    else:
        await call.message.edit_reply_markup(
            call.message.forward_from_message_id,
            reply_markup=await delete_time_client(lang)
        )
    await call.answer()


@user_management_router.callback_query(EditKeysUser.filter())
async def edit_balance_call(
    call: CallbackQuery,
    session: AsyncSession,
    callback_data: EditKeysUser,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    user = await get_person(session, callback_data.id_user)
    keys = await get_key_user(session, callback_data.id_user)
    keys_string = ''
    utc_plus_3 = timezone(timedelta(hours=CONFIG.UTC_time))
    for key in keys:
        time_from_db = datetime.fromtimestamp(key.subscription, tz=utc_plus_3)
        current_time = datetime.now(utc_plus_3)
        time_difference = time_from_db - current_time
        days = time_difference.days
        hours = time_difference.seconds // 3600
        if key.server is not None:
            name = key.server_table.vds_table.location_table.name
            type_vpn_key = ServerManager.VPN_TYPES.get(
                key.server_table.type_vpn
            ).NAME_VPN
        else:
            name = 'no connect'
            type_vpn_key = 'no protocol'
        keys_string += (
            _('user_key_list_admin', lang)
            .format(
                count_key=key.id,
                count_day=days,
                hours=hours,
                type_vpn_key=type_vpn_key,
                name=name,
                count_switch=key.switch_location
            ) + '\n'
        )
    text = Text(
        _('keys_users_edit_admin', lang)
        .format(full_name=user.fullname, telegram_id=user.tgid),
        '\n\n', keys_string
    )
    await call.message.answer(
        **text.as_kwargs(),
        reply_markup=await keys_control(lang, user.tgid)
    )
    await call.answer()


@user_management_router.message(EditUser.add_time)
async def add_time_user_state(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    try:
        if message.text.strip() in btn_text('admin_users_cancellation'):
            await state.clear()
            await message.answer(
                _('back_you_back', lang),
                reply_markup=await admin_user_menu(lang)
            )
            return
        count_day = int(message.text.strip())
        if count_day > 2000:
            await message.answer(_('limit_count_day_sub_m', lang))
            return
    except Exception as e:
        log.info(e, 'incorrect input count day sub')
        await message.answer(_('incorrect_input_count_day_sub', lang))
        return
    try:
        user_data = await state.get_data()
        client = user_data['client']
        await add_time_person(
            session, client.tgid, count_day * (ONE_HOUSE * 24)
        )
        await state.clear()
        await message.answer(
            _('input_count_day_sub_success', lang).format(
                username=client.username
            ),
            reply_markup=await admin_user_menu(lang)
        )
    except Exception as e:
        log.error(e, 'error add time user')
        await message.answer(_('error_not_found', lang))
        await state.clear()
        return
    try:
        client = await get_person(session, client.tgid)
        await message.bot.send_message(
            client.tgid,
            _('donated_days', client.lang),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        log.info(e, 'user block bot')
        await message.answer(
            _('error_input_count_day_sub_success', lang)
        )
        return


@user_management_router.callback_query(DeleteTimeClient.filter())
async def delete_time_user_callback(
    call: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    try:
        user_data = await state.get_data()
        client = user_data['client']
        await person_banned_true(session, client.tgid)
        await delete_key(session, js, remove_key_subject, client)
        await call.message.answer(
            _('user_delete_time_m', lang)
            .format(username=client.username),
            reply_markup=await admin_user_menu(lang)
        )
        await call.answer()
        await state.clear()
    except Exception as e:
        log.error(e, 'error delete key or person banned')
        await call.message.answer(_('error_not_found', lang))
        await state.clear()
        return
    try:
        client = await get_person(session, client.tgid)
        await call.message.bot.send_message(
            client.tgid,
            _('ended_sub_message', client.lang)
        )
    except Exception as e:
        await call.message.answer(_('error_user_delete_time_m', lang))
        log.info(e, 'user block bot')


@user_management_router.message(F.text.in_(btn_text('admin_static_user_btn')))
async def static_user_menu_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await message.answer(
        _('select_menu_item', lang),
        reply_markup=await static_user_menu(lang)
    )


async def string_user_server(client, count, lang):
    return _('show_client_file_str_server', lang, False).format(
        count=count,
        fullname=client.fullname,
        username=client.username,
        telegram_id=int(client.tgid),
        lang_code=client.lang_tg or '❌',
        referral_balance=client.referral_balance,
        group=client.group if client.group is not None else ''
    )


async def get_config_client(session: AsyncSession, server, name):
    serve_manager = ServerManager(server)
    name_location = await get_name_location_server(session, server.id)
    await serve_manager.login()
    return await serve_manager.get_key(
        name=name,
        name_key=name_location,
        key_id=0
    )


@user_management_router.callback_query(MessageAdminUser.filter())
async def message_admin_callback_query(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: MessageAdminUser
):
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.delete()
    await call.message.answer(
        _('input_message_admin_user', lang)
    )
    await state.update_data(tgid=callback_data.id_user)
    await state.set_state(EditUser.input_message_user)
    await call.answer()


@user_management_router.message(EditUser.input_message_user)
async def edit_user_callback_query(
    message: Message,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, message.from_user.id, state)
    text = Text(
        Bold(_('message_from_the_admin', lang)), '\n',
        message.text.strip()
    )
    data = await state.get_data()
    try:
        await message.bot.send_message(int(data['tgid']), **text.as_kwargs())
        await message.answer(
            _('message_from_success', lang),
            reply_markup=await admin_user_menu(lang)
        )
    except Exception as e:
        log.info(e, 'Error send message admin -- user')
        await message.answer(
            _('message_user_block_bot', lang),
            reply_markup=await admin_user_menu(lang)
        )
    await state.clear()


async def list_columns_user(lang):
    return [
        '№',
        _('user_fullname', lang),
        _('user_username', lang),
        _('user_tgid', lang),
        _('user_lang_tg', lang),
        _('user_referral_balance', lang),
        _('user_group', lang),
        _('user_key', lang),
    ]


async def list_user(client, count, not_key=False):

    if not not_key:
        count_key = 0
        for key in client.keys:
            if key.free_key or key.trial_period:
                continue
            count_key += 1
    else:
        count_key = ''
    return [
        count,
        client.fullname,
        client.username,
        int(client.tgid),
        client.lang_tg or '❌',
        client.referral_balance,
        client.group if client.group is not None else '',
        count_key
    ]

async def time_sub_client(client):
    client_data = int(client.subscription) + DEFAULT_UTC
    data = f'{datetime.utcfromtimestamp(client_data).strftime(FORMAT_DATA)}'
    return f'{"" if client.banned is True else data}'
