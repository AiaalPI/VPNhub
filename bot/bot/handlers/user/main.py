import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.formatting import Text, Code
from aiogram.utils.payload import decode_payload
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession

from bot.misc.util import CONFIG
from .edit_or_get_key import (
    choosing_protocol_or_server,
    select_location_callback
)
from .free_vpn import free_vpn_router
from .keys_user import key_router
from .referral_user import referral_router
from .payment_user import callback_user
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.methods.get import (
    get_person,
    get_free_servers,
    get_key_user,
    get_type_vpn,
    get_metric_code
)
from bot.database.methods.update import update_lang
from bot.keyboards.inline.user_inline import (
    choose_server,
    choosing_lang,
    connect_vpn_menu,
    user_menu,
    back_menu_button,
    connect_menu,
)
from bot.misc.language import Localization, get_lang
from bot.misc.callbackData import (
    ChoosingLang,
    ChooseTypeVpn,
    BackTypeVpn, ChooseLocation,
    ConnectMenu, 
)
from bot.filters.main import IsBlocked, IsBlockedCall, check_subs
from bot.database.methods.insert import add_new_person
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

_ = Localization.text
btn_text = Localization.get_reply_button

user_router = Router()
registered_router = Router()
user_router.message.filter(IsBlocked())
user_router.callback_query.filter(IsBlockedCall())
user_router.include_routers(
    callback_user,
    referral_router,
    key_router,
    free_vpn_router
)


async def check_follow(user_id, bot):
    user_channel_status = await bot.get_chat_member(
        chat_id=CONFIG.id_channel,
        user_id=user_id
    )
    return user_channel_status.status != 'left'


@registered_router.callback_query(F.data == 'check_follow_chanel')
async def connect_vpn(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    if await check_follow(call.from_user.id, call.message.bot):
        person = await get_person(session, call.from_user.id)
        await show_start_message(call.message, person, lang)
        await call.answer()
        return
    await call.answer(
        _('no_follow_bad_check', lang),
        show_alert=True
    )

@user_router.callback_query(ConnectMenu.filter())
async def connect_menu_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ConnectMenu,
):
    lang = await get_lang(session, call.from_user.id, state)

    # Нажали "Подключить VPN"
    if callback_data.action == "connect_vpn":
        # Просто переиспользуем твой уже существующий сценарий:
        # эмулируем нажатие старой кнопки "vpn_connect_btn"
        call.data = "vpn_connect_btn"
        await call.answer()
        return

    # Нажали "Пробный период"
    if callback_data.action == "prob_period":
        # пока сделаем тестовую реакцию (потом подключим реальную логику)
        await call.answer("🎁 Пробный период: скоро подключим", show_alert=True)
        return

    await call.answer()

@registered_router.message(Command("start"))
async def command(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    command: Command = None # noqa
):
    if message.from_user.is_bot:
        return
    lang = await get_lang(session, message.from_user.id, state)
    await state.clear()
    is_new_user = False
    if not await get_person(session, message.from_user.id):
        try:
            user_name = f'@{str(message.from_user.username)}'
        except Exception as e:
            log.error(e)
            user_name = str(message.from_user.username)
        metric = await get_metric_code(session, command.args)
        if metric is None:
            reference = decode_payload(command.args) if command.args else None # noqa
        else:
            reference = None
        if reference is not None:

            if reference.isdigit():
                reference = int(reference)
            else:
                reference = None

            if reference != str(message.from_user.id):
                await give_bonus_invitee(session, message, reference, lang)
            else:
                await message.answer(_('referral_error', lang))
                reference = None
        await add_new_person(
            session,
            message.from_user,
            user_name,
            reference,
            metric.id if metric is not None else None,
        )
        is_new_user = True
        await message.answer_photo(
            caption=_('hello_message', lang),
            photo=FSInputFile('bot/img/hello_bot.jpg')
        )
        text_user = Text(
            _('message_new_user', lang), '\n',
            '👤: ' f'@{message.from_user.username}',
            ' ', message.from_user.full_name, '\n',
            'ID:', Code(message.from_user.id)
        )
        try:
            await message.bot.send_message(
                CONFIG.admin_tg_id,
                **text_user.as_kwargs()
            )
        except Exception as e:
            log.error(e)
    person = await get_person(session, message.from_user.id)
    if person.blocked:
        return
    if not await check_subs(message, message.from_user.id, message.bot):
        return
    if is_new_user:
        await show_start_message_new_user(message, person, lang)
    else:
        await show_start_message(message, person, lang)

@user_router.callback_query(F.data.in_(btn_text('general_menu_btn')))
async def back_main_menu(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(lang, call.from_user.id)
    )



@user_router.message(F.text.in_(btn_text('back_general_menu_btn')))
async def back_main_menu(
    message: Message,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, message.from_user.id, state)
    await state.clear()
    await message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(lang, message.from_user.id)
    )


@user_router.callback_query(F.data == 'back_general_menu_btn')
async def back_main_menu(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    await edit_message(
        call.message,
        photo='bot/img/main_menu.jpg',
        reply_markup=await user_menu(lang, call.from_user.id)
    )


@user_router.callback_query(F.data == 'answer_back_general_menu_btn')
async def back_main_menu(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await state.clear()
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(lang, call.from_user.id)
    )

async def show_start_message(message: Message, person, lang):
    await message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(lang, person.tgid)
    )

async def show_start_message_new_user(message: Message, person, lang):
    # Новый пользователь: показываем упрощённый экран (без главного меню)
    await message.answer_photo(
        photo=FSInputFile('bot/img/type_vpn.jpg'),
        reply_markup=await connect_menu(lang, trial_flag=person.trial_period)
    )

    # Если хочешь скрыть пробный период (пауза) — вместо строки выше используй:
    # reply_markup=await connect_menu(lang, trial_flag=True)


@user_router.callback_query(F.data == 'general_menu')
async def get_general_menu(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    person = await get_person(session, call.from_user.id)
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(lang, person.tgid)
    )
    await call.answer()


async def give_bonus_invitee(session, m, reference, lang):
    if reference is None:
        return
    if CONFIG.referral_day == 0:
        await m.bot.send_message(
            reference,
            _('referral_new_user_zero', lang),
        )
        return
    keys = await get_key_user(session, reference)
    await m.bot.send_message(
        reference,
        _('referral_new_user', lang).format(
            day=CONFIG.referral_day,
        ),
        reply_markup=await connect_vpn_menu(
            lang,
            keys,
            'referral_bonus',
        )
    )


@user_router.callback_query(F.data == 'generate_new_key')
async def generate_new_key(
    call: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    state: FSMContext
):
    lang = await get_lang(session, call.from_user.id, state)
    await choosing_protocol_or_server(
        call,
        session,
        js,
        remove_key_subject,
        state,
        call.from_user.id,
        lang,
        back_data='back_general_menu_btn',
        payment = True
    )
    await call.answer()

from bot.misc.callbackData import ConnectMenu

@user_router.callback_query(ConnectMenu.filter())
async def connect_menu_handler(
    call: CallbackQuery,
    callback_data: ConnectMenu,
    session: AsyncSession,
    state: FSMContext,
    js: JetStreamContext,
    remove_key_subject: str,
):
    lang = await get_lang(session, call.from_user.id, state)

    if callback_data.action == "connect_vpn":
        await choosing_protocol_or_server(
            call,
            session,
            js,
            remove_key_subject,
            state,
            call.from_user.id,
            lang,
            payment=True
        )
        await call.answer()
        return

    if callback_data.action == "prob_period":
        # 👇 лог для уверенности
        log.info(f"TRIAL PERIOD pressed by {call.from_user.id}")

        await call.message.answer(
            _("trial_period_info", lang),
            reply_markup=await back_menu_button(lang)
        )
        await call.answer()
        return

@user_router.callback_query(BackTypeVpn.filter())
async def call_choose_server(
    call: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    callback_data: BackTypeVpn,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    user = await get_person(session, call.from_user.id)
    all_types_vpn = await get_type_vpn(session, user.group)
    if len(all_types_vpn) == 1:
        await state.clear()
        await edit_message(
            call.message,
            photo='bot/img/main_menu.jpg',
            reply_markup=await user_menu(lang, call.from_user.id)
        )
        return
    await choosing_protocol_or_server(
        call,
        session,
        js,
        remove_key_subject,
        state,
        call.from_user.id,
        lang,
        key_id=callback_data.key_id,
        back_data='vpn_connect_btn'
    )


@user_router.callback_query(ChooseTypeVpn.filter())
async def choose_server_free(
    call: CallbackQuery,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    callback_data: ChooseTypeVpn,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    user = await get_person(session, call.from_user.id)
    try:
        all_active_location = await get_free_servers(
            session, user.group, callback_data.type_vpn
        )
    except FileNotFoundError:
        log.info('Not free servers -- OK')
        await call.message.answer(_('not_server', lang))
        await call.answer()
        return
    if len(all_active_location) == 1:
        await select_location_callback(
            call,
            session,
            callback_data=ChooseLocation(
                id_location=all_active_location[0].id,
                key_id=callback_data.key_id,
                type_vpn=callback_data.type_vpn,
                payment=callback_data.payment
            ),
            js=js,
            remove_key_subject=remove_key_subject,
            state=state
        )
    else:
        await edit_message(
            call.message,
            photo='bot/img/locations.jpg',
            caption=_('choosing_connect_location', lang),
            reply_markup=await choose_server(
                all_active_location,
                callback_data.type_vpn,
                lang,
                callback_data.key_id,
                payment=callback_data.payment
            )
        )


@user_router.callback_query(F.data.in_(btn_text('language_btn')))
async def choose_server_user(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await choose_lang(call.message, lang)


@user_router.callback_query(F.data.in_('language_btn'))
async def choose_server_user(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    try:
        await call.message.delete()
    except Exception:
        log.info('error delete message')
    await choose_lang(call.message, lang)


async def choose_lang(message, lang):
    await message.answer(
        _('select_language', lang),
        reply_markup=await choosing_lang()
    )


@user_router.callback_query(ChoosingLang.filter())
async def deposit_balance(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    callback_data: ChoosingLang
) -> None:
    lang = callback_data.lang
    await update_lang(session, lang, call.from_user.id)
    await state.update_data(lang=lang)
    person = await get_person(session, call.from_user.id)
    try:
        await call.message.delete()
    except Exception as e:
        log.info(f'not delete message langs\n{e}')
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/main_menu.jpg'),
        reply_markup=await user_menu(person.lang, person.tgid)
    )
    await call.answer()


@user_router.callback_query(F.data.in_(btn_text('about_vpn_btn')))
async def info_message_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await call.message.answer_photo(
        photo=FSInputFile('bot/img/about.jpg'),
        caption=_('about_message', lang)
        .format(name_bot=CONFIG.name),
        reply_markup = await back_menu_button(lang)
    )


@user_router.callback_query(F.data.in_('about_vpn_btn'))
async def info_message_handler(
    call: CallbackQuery,
    session: AsyncSession,
    state: FSMContext
) -> None:
    lang = await get_lang(session, call.from_user.id, state)
    await edit_message(
        call.message,
        photo='bot/img/about.jpg',
        caption=_('about_message', lang)
        .format(name_bot=CONFIG.name),
        reply_markup=await back_menu_button(lang)
    )
