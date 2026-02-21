from datetime import datetime, timezone, timedelta

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from remnawave.models.hwid import HwidDeviceDto

from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.callbackData import (
    ChoosingMonths,
    ChoosingPrise,
    ChooseLocation,
    MessageAdminUser,
    ChoosingLang,
    ChooseTypeVpn,
    ConnectMenu,
    ChooseTypeVpnHelp,
    DonatePrice,
    EditKey,
    ShowKey,
    BackTypeVpn,
    ExtendKey,
    PromoCodeChoosing,
    DetailKey, ReferralKeys, TrialPeriod, ShowUserDevices, RemoveUserDevices
)
from bot.misc.language import Localization
from bot.misc.util import CONFIG

_ = Localization.text


async def user_menu(lang, id_user) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    kb.button(
        text=_('vpn_connect_btn', lang),
        callback_data='vpn_connect_btn',
    )
    kb.button(
        text=_('affiliate_btn', lang),
        callback_data='affiliate_btn',
    )
    kb.button(
        text=_('language_btn', lang),
        callback_data='language_btn',
    )
    kb.button(
        text=_('help_btn', lang),
        callback_data='help_btn',
    )
    kb.button(
        text=_('about_vpn_btn', lang),
        callback_data='about_vpn_btn',
    )

    if CONFIG.is_admin(id_user):
        kb.button(
            text=_('admin_panel_btn', lang),
            callback_data='admin_panel_btn',
        )

    kb.adjust(1, 2, 2)
    return kb.as_markup(resize_keyboard=True)


async def back_menu_button(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    await back_menu(kb, lang)
    return kb.as_markup(resize_keyboard=True)


async def back_menu(kb, lang) -> InlineKeyboardBuilder:
    return kb.button(
        text=_('back_general_menu_btn', lang),
        callback_data='back_general_menu_btn',
    )


async def replenishment(
    config, price,
    lang, type_pay,
    key_id=0,
    id_prot=0,
    id_loc=0,
    month_count=0
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    adjust = 2
    if config.yookassa_shop_id != "" and config.yookassa_secret_key != "":
        kb.button(
            text=_('payments_yookassa_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='KassaSmart',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.yoomoney_token != "" and config.yoomoney_wallet_token != "":
        kb.button(
            text=_('payments_yoomoney_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='YooMoney',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.cryptomus_key != "" and config.cryptomus_uuid != "":
        kb.button(
            text=_('payments_cryptomus_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='Cryptomus',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.crypto_bot_api != '':
        kb.button(
            text=_('payments_cyrptobot_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='CryptoBot',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.lava_token_secret != "" and config.lava_id_project != "":
        kb.button(
            text=_('payments_lava_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='Lava',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.token_stars != 'off':
        kb.button(
            text=_('payments_stars_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='Stars',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.wawa_token_card != '':
        kb.button(
            text=_('payments_wawa_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='Wawa',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.wawa_token_sbp != '':
        kb.button(
            text=_('payments_wawa_spb_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='WawaSpb',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.wawa_token_visa != '':
        kb.button(
            text=_('payments_wawa_visa_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='WawaVisa',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if config.heleket_key != "" and config.heleket_uuid != "":
        kb.button(
            text=_('payments_heleket_btn', lang),
            callback_data=ChoosingPrise(
                price=price, payment='Heleket',
                type_pay=type_pay, key_id=key_id,
                id_prot=id_prot, id_loc=id_loc,
                month_count=month_count
            )
        )
    if (
            config.yookassa_shop_id == ""
            and config.yoomoney_token == ""
            and config.lava_token_secret == ""
            and config.cryptomus_key == ""
            and config.heleket_key == ""
            and config.crypto_bot_api == ""
            and config.wawa_token_card == ""
            and config.wawa_token_sbp == ""
            and config.wawa_token_visa == ""
            and config.token_stars == 'off'
    ):
        kb.button(text=_('payments_not_btn_1', lang), callback_data='none')
        kb.button(text=_('payments_not_btn_2', lang), callback_data='none')
        adjust = 1
    kb.button(
        text=_('back_general_menu_btn', lang),
        callback_data='answer_back_general_menu_btn',
    )
    kb.adjust(adjust)
    return kb.as_markup()


async def choosing_promo_code(
    lang, promo_codes,
    price, type_pay,
    key_id=0,
    id_prot=0, id_loc=0,
    month_count=0,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for promo_code in promo_codes:
        kb.button(
            text=_('promo_code_menu_btn', lang)
            .format(
                name_promo=promo_code.text, percent=promo_code.percent
            ),
            callback_data=PromoCodeChoosing(
                id_promo=promo_code.id,
                percent=promo_code.percent,
                price=price,
                type_pay=type_pay,
                key_id=key_id,
                id_prot=id_prot,
                id_loc=id_loc,
                month_count=month_count
            )
        )
    kb.button(
        text=_('not_promo_code_menu_btn', lang),
        callback_data=PromoCodeChoosing(
            id_promo=0,
            percent=0,
            price=price,
            type_pay=type_pay,
            key_id=key_id,
            id_prot=id_prot,
            id_loc=id_loc,
            month_count=month_count
        )
    )
    kb.adjust(1)
    return kb.as_markup()


async def connect_menu(lang, trial_flag) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('vpn_connect_btn', lang),
        callback_data=ConnectMenu(action='connect_vpn')
    )
    if not trial_flag and CONFIG.trial_period != 0:
        kb.button(
            text=_('trial_period_btn', lang),
            callback_data=ConnectMenu(action='prob_period')
        )
    kb.adjust(1)
    return kb.as_markup()


async def choose_type_vpn(
    all_type_vpn,
    lang,
    key_id=0,
    back_data=None,
    payment:bool = False
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    adjust = [2, 1]
    for key, item in ServerManager.VPN_TYPES.items():
        if key in all_type_vpn:
            kb.button(
                text=item.NAME_VPN,
                callback_data=ChooseTypeVpn(
                    type_vpn=key,
                    key_id=key_id,
                    payment=payment
                )
            )
    if len(all_type_vpn) == 0:
        kb.button(
            text=_('type_vpn_none', lang),
            callback_data='none protocol'
        )
        adjust = [1]
    if back_data is not None:
        kb.button(
            text=_('back_general_menu_btn', lang),
            callback_data=back_data,
        )
    kb.adjust(*adjust)
    return kb.as_markup()


async def renew(
        config, lang,
        type_pay, back_data,
        key_id=0, trial_flag=True,
        id_protocol=0, id_location=0
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    adjust = [2, 2, 1]
    if not trial_flag and CONFIG.trial_period != 0:
        kb.button(
            text=_('trial_period_btn', lang),
            callback_data=TrialPeriod(
                id_prot=id_protocol,
                id_loc=id_location
            )
        )
        adjust.insert(0, 1)
    kb.button(
        text=_('to_extend_month_1_btn', lang)
        .format(price=config.month_cost[0]),
        callback_data=ChoosingMonths(
            price=str(config.month_cost[0]),
            month_count=1,
            type_pay=type_pay,
            key_id=key_id,
            id_prot=id_protocol,
            id_loc=id_location
        )
    )
    kb.button(
        text=_('to_extend_month_2_btn', lang)
        .format(price=config.month_cost[1]),
        callback_data=ChoosingMonths(
            price=str(config.month_cost[1]),
            month_count=3,
            type_pay=type_pay,
            key_id=key_id,
            id_prot = id_protocol,
            id_loc = id_location
        )
    )
    kb.button(
        text=_('to_extend_month_3_btn', lang)
        .format(price=config.month_cost[2]),
        callback_data=ChoosingMonths(
            price=str(config.month_cost[2]),
            month_count=6,
            type_pay=type_pay,
            key_id=key_id,
            id_prot=id_protocol,
            id_loc=id_location
        )
    )
    kb.button(
        text=_('to_extend_month_4_btn', lang)
        .format(price=config.month_cost[3]),
        callback_data=ChoosingMonths(
            price=str(config.month_cost[3]),
            month_count=12,
            type_pay=type_pay,
            key_id=key_id,
            id_prot=id_protocol,
            id_loc=id_location
        )
    )
    kb.button(
        text=_('back_general_menu_btn', lang),
        callback_data=back_data,
    )
    kb.adjust(*adjust)
    return kb.as_markup()


async def price_menu(config, payment) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for price in config.deposit:
        kb.button(
            text=f'{price} ₽',
            callback_data=ChoosingPrise(
                price=int(price),
                payment=payment
            )
        )
    kb.adjust(1)
    return kb.as_markup()


async def choosing_lang() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for lang, cls in Localization.ALL_Languages.items():
        kb.button(text=cls, callback_data=ChoosingLang(lang=lang))
    kb.adjust(1)
    return kb.as_markup()


async def pay_and_check(
    link_invoice: str,
    lang,
    webapp=False
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not webapp:
        kb.button(text=_('user_pay_sub_btn', lang), url=link_invoice)
    else:
        kb.button(
            text=_('user_pay_sub_btn', lang),
            web_app=WebAppInfo(url=link_invoice)
        )
    kb.button(
        text=_('back_general_menu_btn', lang),
        callback_data='answer_back_general_menu_btn',
    )
    kb.adjust(1)
    return kb.as_markup()


async def pay_stars(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=_('user_pay_sub_btn', lang), pay=True)
    kb.button(
        text=_('back_general_menu_btn', lang),
        callback_data='answer_back_general_menu_btn',
    )
    kb.adjust(1)
    return kb.as_markup()


async def instruction_manual(
    lang,
    type_vpn,
    link_sub=None,
    key_id=None,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if link_sub is not None:
        kb.button(
            text=_('sub_open_btn', lang),
            url=link_sub
        )
    if type_vpn == 0:
        kb.button(
            text=_('instruction_use_iphone_btn', lang),
            url=_('instruction_iphone_outline', lang, False)
        )
        kb.button(
            text=_('instruction_use_android_btn', lang),
            url=_('instruction_android_outline', lang, False)
        )
        kb.button(
            text=_('instruction_use_pc_btn', lang),
            url=_('instruction_windows_outline', lang, False)
        )
    elif type_vpn == 1 or type_vpn == 2 or type_vpn == 5:
        kb.button(
            text=_('instruction_use_iphone_btn', lang),
            url=_('instruction_iphone_vless', lang, False)
        )
        kb.button(
            text=_('instruction_use_android_btn', lang),
            url=_('instruction_android_vless', lang, False)
        )
        kb.button(
            text=_('instruction_use_pc_btn', lang),
            url=_('instruction_windows_vless', lang, False)
        )
    elif type_vpn == 3:
        kb.button(
            text=_('instruction_use_iphone_btn', lang),
            url=_('instruction_iphone_wg', lang, False)
        )
        kb.button(
            text=_('instruction_use_android_btn', lang),
            url=_('instruction_android_wg', lang, False)
        )
        kb.button(
            text=_('instruction_use_pc_btn', lang),
            url=_('instruction_windows_wg', lang, False)
        )
    elif type_vpn == 4:
        kb.button(
            text=_('instruction_use_iphone_btn', lang),
            url=_('instruction_iphone_amnezia_wg', lang, False)
        )
        kb.button(
            text=_('instruction_use_android_btn', lang),
            url=_('instruction_android_amnezia_wg', lang, False)
        )
        kb.button(
            text=_('instruction_use_pc_btn', lang),
            url=_('instruction_windows_amnezia_wg', lang, False)
        )
    elif type_vpn == 6:
        kb.button(
            text=_('remna_user_devices', lang),
            callback_data=ShowUserDevices(key_id=key_id)
        )
    else:
        raise NotImplemented(f'Not found type VPN {type_vpn}')
    kb.button(
        text=_('instruction_check_vpn_btn', lang), url='https://2ip.ru/'
    )
    kb.button(
        text=_('back_general_menu_btn', lang),
        callback_data='answer_back_general_menu_btn',
    )
    kb.adjust(1)
    return kb.as_markup()


async def back_instructions(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('back_type_vpn', lang),
        callback_data='back_instructions'
    )
    kb.adjust(1)
    return kb.as_markup()


async def share_link(ref_link, lang, ref_balance=None) -> InlineKeyboardMarkup:
    link = f'https://t.me/share/url?url={ref_link}'
    kb = InlineKeyboardBuilder()
    kb.button(text=_('user_share_btn', lang), url=link)
    if ref_balance is not None:
        if ref_balance >= CONFIG.minimum_withdrawal_amount:
            kb.button(
                text=_('withdraw_funds_btn', lang)
                .format(
                    min_withdrawal_amount=CONFIG.minimum_withdrawal_amount
                ),
                callback_data='withdrawal_of_funds'
            )
        else:
            kb.button(
                text=_('enough_funds_withdraw_btn', lang)
                .format(
                    min_withdrawal_amount=CONFIG.minimum_withdrawal_amount
                ),
                callback_data='none'
            )
    await back_menu(kb, lang)
    kb.adjust(1)
    return kb.as_markup()


async def promo_code_button(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=_('write_the_promo_btn', lang), callback_data='promo_code')
    await back_menu(kb, lang)
    kb.adjust(1)
    return kb.as_markup()


async def choose_server(
    all_active_location,
    type_vpn,
    lang,
    key_id=0,
    payment=False
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for location in all_active_location:
        text_button = location.name
        kb.button(
            text=text_button,
            callback_data=ChooseLocation(
                id_location=location.id,
                key_id=key_id,
                type_vpn=type_vpn,
                payment=payment
            )
        )
    if payment:
        kb.button(
            text=_('back_type_vpn', lang),
            callback_data='back_general_menu_btn'
        )
    else:
        kb.button(
            text=_('back_type_vpn', lang),
            callback_data=BackTypeVpn(key_id=key_id)
        )
    kb.adjust(1)
    return kb.as_markup()


async def message_admin_user(tgid_user, lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_user_send_reply_btn', lang),
        callback_data=MessageAdminUser(id_user=tgid_user)
    )
    kb.adjust(1)
    return kb.as_markup()


async def back_help_menu(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('back_type_vpn', lang),
        callback_data='back_help_menu'
    )
    kb.adjust(1)
    return kb.as_markup()


async def choose_type_vpn_help(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    # kb.button(text='Outline 🪐', callback_data=ChooseTypeVpnHelp(type_vpn=0))
    kb.button(text='Ꮩlᴇss', callback_data=ChooseTypeVpnHelp(type_vpn=1))
    kb.button(
        text='ᏚhᴀdᴏwᏚᴏᴄᴋs', callback_data=ChooseTypeVpnHelp(type_vpn=2)
    )
    kb.button(
        text=_('back_type_vpn', lang),
        callback_data='back_help_menu'
    )
    kb.adjust(1)
    return kb.as_markup()


async def donate_menu(lang) -> InlineKeyboardMarkup:
    donate_price = [99, 499, 999]
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f'{donate_price[0]}₽',
        callback_data=DonatePrice(price=donate_price[0])
    )
    kb.button(
        text=f'{donate_price[1]}₽',
        callback_data=DonatePrice(price=donate_price[1])
    )
    kb.button(
        text=f'{donate_price[2]}₽',
        callback_data=DonatePrice(price=donate_price[2])
    )
    kb.button(
        text=_('donate_input_price', lang),
        callback_data=DonatePrice(price=0)
    )
    kb.row(
        InlineKeyboardButton(
            text=_('donate_list', lang),
            callback_data='donate_list'
        )
    )
    await back_menu(kb, lang)
    kb.adjust(3, 1, 1)
    return kb.as_markup()


async def back_donate_menu(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('back_type_vpn', lang),
        callback_data='back_donate_menu'
    )
    kb.adjust(1)
    return kb.as_markup()


async def connect_vpn_menu(
    lang,
    keys,
    id_detail=None,
    add_day=CONFIG.referral_day
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    count_key = 1
    adjust = []
    if id_detail == 'referral_bonus':
        kb.button(
            text=_('user_key_list_new_key', lang),
            callback_data=ReferralKeys(key_id=0, add_day=add_day)
        )
    else:
        kb.button(
            text=_('user_key_list_new_key', lang),
            callback_data='generate_new_key'
        )
    adjust.append(1)
    utc_plus_3 = timezone(timedelta(hours=CONFIG.UTC_time))
    for key in keys:
        time_from_db = datetime.fromtimestamp(key.subscription, tz=utc_plus_3)
        current_time = datetime.now(utc_plus_3)
        time_difference = time_from_db - current_time
        time = time_difference.days
        if time == 0:
            time = _('hours_small', lang).format(
                hours=time_difference.seconds // 3600
            )
        else:
            time = _('day_small', lang).format(
                day=time
            )
        if key.server is not None:
            name = key.server_table.vds_table.location_table.name
            type_vpn_key = ServerManager.VPN_TYPES.get(
                key.server_table.type_vpn
            ).NAME_VPN
        else:
            name = ''
            type_vpn_key = _('no_connect_key_message', lang)
        if id_detail is not None and id_detail == key.id:
            kb.button(
                text=_('user_key_get', lang),
                callback_data=ShowKey(key_id=key.id)
            )
            kb.button(
                text=_('user_key_extend', lang),
                callback_data=ExtendKey(key_id=key.id)
            )
            if key.server is not None and CONFIG.is_work_edit_key:
                kb.button(
                    text=_('user_key_edit', lang),
                    callback_data=EditKey(key_id=key.id)
                )
                adjust.append(3)
            else:
                adjust.append(2)
            count_key += 1
            continue
        if id_detail == 'referral_bonus':
            data = ReferralKeys(key_id=key.id, add_day=CONFIG.referral_day)
        else:
            data = DetailKey(key_id=key.id)
        kb.button(
            text=_('user_key_list', lang)
            .format(
                count_key=count_key,
                count_day=time,
                type_vpn_key=type_vpn_key,
                name=name
            ),
            callback_data=data
        )
        count_key += 1
        adjust.append(1)
    await back_menu(kb, lang)
    adjust.append(1)
    kb.adjust(*adjust)
    return kb.as_markup()


async def check_follow_chanel(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=CONFIG.name_channel,
        url=CONFIG.link_channel
    )
    kb.button(
        text=_('no_follow_button', lang),
        callback_data='check_follow_chanel'
    )
    kb.adjust(1)
    return kb.as_markup()


async def trial_pay_button(lang, price) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('payment_button', lang),
        callback_data=ChoosingPrise(
            price=price, payment='KassaSmart',
            type_pay=CONFIG.type_payment.get(4), key_id=0
        )
    )
    kb.adjust(1)
    return kb.as_markup()


async def mailing_button_message(lang, text) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if text == 'not_button_mailing_btn':
        return kb.as_markup()
    kb.button(
        text=_(text, lang),
        callback_data=_(text, lang),
    )
    kb.adjust(1)
    return kb.as_markup()


async def user_device_remove(
    lang,
    key_id: int,
    user_devices: list[HwidDeviceDto]
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for device in user_devices:
        kb.button(
            text=_('remove_device_btn', lang).format(
                name=device.device_model
            ),
            callback_data=RemoveUserDevices(hwid=device.hwid, key_id=key_id),
        )
    await back_menu(kb, lang)
    kb.adjust(1)
    return kb.as_markup()
