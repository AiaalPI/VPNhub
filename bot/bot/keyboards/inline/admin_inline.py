from typing import Sequence

from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram_widgets.pagination import KeyboardPaginator
from remnawave.models import GetAllInternalSquadsResponseDto

from bot.database.models.main import Metric
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.callbackData import (
    ChoosingConnectionMethod,
    ChoosingPanel,
    ServerWork,
    ServerUserList,
    DeleteTimeClient,
    DeleteStaticUser,
    MissingMessage,
    ChoosingVPN,
    PromocodeDelete,
    AplicationReferral,
    ApplicationSuccess,
    MessageAdminUser,
    EditKeysUser,
    GroupAction,
    ServerSwitchPay,
    EditKeysAdmin,
    BlockedUserPanel,
    ButtonsMailing,
    EditLocations,
    Locations,
    VdsList,
    AddVds,
    EditVds,
    ProtocolList,
    AddProtocol,
    ServerDelete,
    ChooseLocations,
    ChooseVdsList,
    ChooseProtocolList,
    ChoosingTypeServer,
    ShowMetric,
    RemoveMetric,
    ServerAutoWork,
    StatusUserPanel,
    SelectTypePromoCode,
    EditInSquad,
    SelectNewInSquad,
    SelectInSquad
)
from bot.misc.language import Localization

_ = Localization.text


async def choosing_connection() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text='HTTP 🔌',
        callback_data=ChoosingConnectionMethod(connection=False)
    )
    kb.button(
        text='HTTPS 🔌',
        callback_data=ChoosingConnectionMethod(connection=True)
    )
    kb.adjust(2)
    return kb.as_markup()


async def choosing_vpn(id_vds, lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, item in ServerManager.VPN_TYPES.items():
        kb.button(
            text=item.NAME_VPN,
            callback_data=ChoosingVPN(type=key)
        )
    kb.button(
        text=_('admin_back_users_menu_btn', lang),
        callback_data=EditVds(action='control_protocol', id=id_vds)
    )
    kb.adjust(1)
    return kb.as_markup()


async def choosing_panel() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text='Sanaei 🖲',
        callback_data=ChoosingPanel(panel='sanaei')
    )
    kb.button(
        text='Alireza 🕹',
        callback_data=ChoosingPanel(panel='alireza')
    )
    kb.adjust(2)
    return kb.as_markup()


async def skip_input_caddy_token(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_skip_btn', lang),
        callback_data='skip_input_caddy_token'
    )
    kb.adjust(2)
    return kb.as_markup()


async def locations_list(
        locations,
        lang,
        static_user_action=False
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not static_user_action:
        kb.button(
            text=_('admin_locations_add_btn', lang),
            callback_data='add_location'
        )
        callback_data = Locations
    else:
        callback_data = ChooseLocations
    for location in locations:
        group = '' if location.group is None else location.group
        work = (
            _('server_use_s', lang)) \
            if location.work else (
            _('server_not_use_s', lang)
        )
        text = (
             f'{location.name} '
             f'{len(location.vds)} 🕋'
             f'{group} '
             f'{work}'
        )
        kb.button(
            text=text,
            callback_data=callback_data(id=location.id)
        )
    if len(locations) > 0:
        kb.button(
            text=_('statistic_locations', lang),
            callback_data='locations_statistic'
        )
    kb.adjust(1)
    return kb.as_markup()


async def vds_list_menu(
    location_id,
    vds_list,
    lang,
    static_user_action=False
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not static_user_action:
        kb.button(
            text=_('admin_locations_add_btn', lang),
            callback_data=AddVds(location_id=location_id)
        )
        callback_data = VdsList
        back_data = Locations(id=location_id)
    else:
        callback_data = ChooseVdsList
        back_data = 'back_choose_locations'
    for vds in vds_list:
        work = (
            _('server_use_s', lang)) \
            if vds.work else (
            _('server_not_use_s', lang)
        )
        kb.button(
            text=f'{vds.ip} {work} {len(vds.servers)} 🔐',
            callback_data=callback_data(location_id=location_id, vds_id=vds.id)
        )
    kb.button(
        text=_('admin_back_users_menu_btn', lang),
        callback_data=back_data
    )
    kb.adjust(1)
    return kb.as_markup()


async def protocol_list_menu(
        location_id, vds_id, protocol_list, lang, static_user_action=False
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not static_user_action:
        kb.button(
            text=_('admin_vds_add_protocol_btn', lang),
            callback_data=AddProtocol(vds_id=vds_id)
        )
        callback_data = ProtocolList
        back_data = VdsList(location_id=location_id, vds_id=vds_id)
    else:
        callback_data = ChooseProtocolList
        back_data = ChooseLocations(id=location_id)
    for protocol in protocol_list:
        work = (
            _('server_use_s', lang)) \
            if protocol.work else (
            _('server_not_use_s', lang)
        )
        type_vpn = ServerManager.VPN_TYPES.get(protocol.type_vpn).NAME_VPN
        kb.button(
            text=f'{type_vpn} {work} {protocol.actual_space} 👥',
            callback_data=callback_data(vds_id=vds_id, protocol_id=protocol.id)
        )
    kb.button(
        text=_('admin_back_users_menu_btn', lang),
        callback_data=back_data
    )
    kb.adjust(1)
    return kb.as_markup()


async def location_menu(lang, id_location, pay_switch) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_locations_control_vds_btn', lang),
        callback_data=EditLocations(action='control_vds', id=id_location)
    )
    kb.button(
        text=_('admin_locations_work_btn', lang),
        callback_data=EditLocations(action='work', id=id_location)
    )
    kb.button(
        text=_('admin_locations_edit_btn', lang),
        callback_data=EditLocations(action='edit', id=id_location)
    )
    kb.button(
        text=_('admin_locations_del_btn', lang),
        callback_data=EditLocations(action='del', id=id_location)
    )
    text_switch = _('not_pay_switch_server_btn', lang) \
        if pay_switch else _('pay_switch_server_btn', lang)
    kb.button(
        text=text_switch,
        callback_data=ServerSwitchPay(
            id_location=id_location,
            action=not pay_switch
        )
    )
    kb.button(
        text=_('admin_back_users_menu_btn', lang),
        callback_data='back_location_list'
    )
    kb.adjust(1, 1, 2, 1)
    return kb.as_markup()


async def vds_menu(lang, id_vds, id_location) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_vds_control_protocol_btn', lang),
        callback_data=EditVds(action='control_protocol', id=id_vds)
    )
    kb.button(
        text=_('admin_vds_work_btn', lang),
        callback_data=EditVds(action='work', id=id_vds)
    )
    kb.button(
        text=_('admin_vds_edit_name_btn', lang),
        callback_data=EditVds(action='edit_name', id=id_vds)
    )
    kb.button(
        text=_('admin_vds_edit_password_btn', lang),
        callback_data=EditVds(action='edit_pass', id=id_vds)
    )
    kb.button(
        text=_('admin_vds_edit_ip_btn', lang),
        callback_data=EditVds(action='edit_ip', id=id_vds)
    )
    kb.button(
        text=_('admin_vds_edit_limit_btn', lang),
        callback_data=EditVds(action='edit_limit', id=id_vds)
    )
    kb.button(
        text=_('admin_vds_del_btn', lang),
        callback_data=EditVds(action='del', id=id_vds)
    )
    kb.button(
        text=_('admin_back_users_menu_btn', lang),
        callback_data=EditLocations(action='control_vds', id=id_location)
    )
    kb.adjust(1, 1, 2, 2, 1)
    return kb.as_markup()


async def server_control(protocol, lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('list_user_server_btn', lang),
        callback_data=ServerUserList(id_protocol=protocol.id, action=True)
    )
    if protocol.work:
        kb.button(
            text=_('not_uses_server_btn', lang),
            callback_data=ServerWork(work=False, id_protocol=protocol.id)
        )
    else:
        kb.button(
            text=_('uses_server_btn', lang),
            callback_data=ServerWork(work=True, id_protocol=protocol.id)
        )
    if protocol.auto_work:
        kb.button(
            text=_('hidden_server_btn', lang),
            callback_data=ServerAutoWork(work=False, id_protocol=protocol.id)
        )
    else:
        kb.button(
            text=_('show_server_btn', lang),
            callback_data=ServerAutoWork(work=True, id_protocol=protocol.id)
        )
    kb.button(
        text=_('delete_key_server_btn', lang),
        callback_data=ServerUserList(id_protocol=protocol.id, action=False)
    )
    kb.button(
        text=_('admin_server_delete_btn', lang),
        callback_data=ServerDelete(id_protocol=protocol.id)
    )
    if protocol.type_vpn == 6:
        kb.button(
            text=_('eit_internal_squad_btn', lang),
            callback_data=EditInSquad(id_protocol=protocol.id)
        )
    kb.button(
        text=_('admin_back_users_menu_btn', lang),
        callback_data=EditVds(action='control_protocol', id=protocol.vds)
    )
    kb.adjust(1,2,2,1)
    return kb.as_markup()


async def edit_client_menu(
    tgid_user,
    lang,
    blocked,
    status
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_user_edit_keys_btn', lang),
        callback_data=EditKeysUser(id_user=tgid_user)
    )
    if status:
        kb.button(
            text=_('edit_client_default', lang),
            callback_data=StatusUserPanel(status=status, id_user=tgid_user)
        )
    else:
        kb.button(
            text=_('edit_client_partner', lang),
            callback_data=StatusUserPanel(status=status, id_user=tgid_user)
        )
    if not blocked:
        kb.button(
            text=_('edit_client_blocked', lang),
            callback_data=BlockedUserPanel(action='blocked', id_user=tgid_user)
        )
    else:
        kb.button(
            text=_('edit_client_unblocked', lang),
            callback_data=BlockedUserPanel(
                action='unblocked', id_user=tgid_user
            )
        )
    kb.button(
        text=_('admin_user_message_client_btn', lang),
        callback_data=MessageAdminUser(id_user=tgid_user)
    )
    kb.adjust(1)
    return kb.as_markup()


async def delete_time_client(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('definitely_dropping_btn', lang),
        callback_data=DeleteTimeClient(delete_time=True)
    )
    kb.adjust(1)
    return kb.as_markup()


async def delete_static_user(name, protocol_id, lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('delete_static_user_btn', lang),
        callback_data=DeleteStaticUser(name=name, protocol_id=protocol_id)
    )
    kb.adjust(1)
    return kb.as_markup()


async def missing_user_menu(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_user_mailing_all_btn', lang),
        callback_data=MissingMessage(option='all')
    )
    kb.button(
        text=_('admin_user_mailing_sub_btn', lang),
        callback_data=MissingMessage(option='sub')
    )
    kb.button(
        text=_('admin_user_mailing_not_sub_btn', lang),
        callback_data=MissingMessage(option='no')
    )
    kb.button(
        text=_('admin_user_mailing_update_btn', lang),
        callback_data=MissingMessage(option='update')
    )
    kb.adjust(1)
    return kb.as_markup()


async def promocode_menu(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('promo_add_new_btn', lang),
        callback_data='new_promo'
    )
    kb.button(
        text=_('promo_show_all_btn', lang),
        callback_data='show_promo'
    )
    kb.adjust(1)
    return kb.as_markup()


async def application_referral_menu(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('applications_show_all_btn', lang),
        callback_data=AplicationReferral(type=True)
    )
    kb.button(
        text=_('applications_show_active_btn', lang),
        callback_data=AplicationReferral(type=False)
    )
    kb.adjust(1)
    return kb.as_markup()


async def promocode_delete(id_promo, mes_id, lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('delete_static_user_btn', lang),
        callback_data=PromocodeDelete(id_promo=id_promo, mes_id=mes_id)
    )
    kb.adjust(1)
    return kb.as_markup()


async def application_success(
        id_application,
        mes_id,
        lang
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('applications_success_btn', lang),
        callback_data=ApplicationSuccess(
            id_application=id_application,
            mes_id=mes_id
        )
    )
    kb.adjust(1)
    return kb.as_markup()


async def group_control(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_groups_client_show_btn', lang),
        callback_data=GroupAction(action='show')
    )
    kb.button(
        text=_('admin_groups_client_add_btn', lang),
        callback_data=GroupAction(action='add')
    )
    kb.button(
        text=_('admin_groups_client_exclude_btn', lang),
        callback_data=GroupAction(action='exclude')
    )
    kb.button(
        text=_('admin_groups_client_delete_btn', lang),
        callback_data=GroupAction(action='delete')
    )
    kb.adjust(1)
    return kb.as_markup()


async def keys_control(lang, id_user) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('user_key_list_new_key', lang),
        callback_data=EditKeysAdmin(
            action='new_key',
            id_user=id_user
        )
    )
    kb.button(
        text=_('key_control_edit_time', lang),
        callback_data=EditKeysAdmin(
            action='edit_time',
            id_user=id_user
        )
    )
    kb.button(
        text=_('key_control_update_swith', lang),
        callback_data=EditKeysAdmin(
            action='swith_update',
            id_user=id_user
        )
    )
    kb.button(
        text=_('key_control_delete_key', lang),
        callback_data=EditKeysAdmin(
            action='delete_key',
            id_user=id_user
        )
    )
    kb.adjust(1)
    return kb.as_markup()


async def buttons_mailing(lang, config) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key in config.type_buttons_mailing:
        kb.button(
            text=_(key, lang),
            callback_data=ButtonsMailing(action=key)
        )
    kb.adjust(2)
    return kb.as_markup()


async def type_server_menu(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_free_server_btn', lang),
        callback_data=ChoosingTypeServer(type_server=True)
    )
    kb.button(
        text=_('admin_not_free_server_btn', lang),
        callback_data=ChoosingTypeServer(type_server=False)
    )
    kb.adjust(2)
    return kb.as_markup()


async def metric_remove_back(lang, id_metric) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('admin_locations_del_btn', lang),
        callback_data=RemoveMetric(id_metric=id_metric)
    )
    kb.button(
        text='ㅤ',
        callback_data='none'
    )
    kb.button(
        text=_('back_subscription_menu_btn', lang),
        callback_data='show_all_metrics'
    )
    kb.adjust(1)
    return kb.as_markup()


async def metric_menu(
    router: Router,
    lang: str,
    all_metric: Sequence[Metric],
):
    """Функция возвращающая пагинатор"""
    buttons = []
    for metric in all_metric:
        len_user = str(len(metric.users)) + '👤 ' + metric.text
        buttons.append(
            InlineKeyboardButton(
                text=len_user,
                callback_data=ShowMetric(id_metric=metric.id).pack()
            )
        )
    optional_buttons = [
        [
            InlineKeyboardButton(
                text=_('admin_locations_add_btn', lang),
                callback_data='add_metric'
            )
        ]
    ]
    if len(all_metric) != 0:
        optional_buttons.append(
            [
                InlineKeyboardButton(
                    text=_('admin_statistic_metric', lang),
                    callback_data='statistic_metric'
                )
            ]
        )
    paginator = KeyboardPaginator(
        data=buttons,
        per_page=10,
        per_row=2,
        additional_buttons=optional_buttons,
        router=router
    )
    return paginator


async def type_promo_code(lang) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_('promo_sell_btn', lang),
        callback_data=SelectTypePromoCode(type_promo=1)
    )
    kb.button(
        text=_('promo_day_btn', lang),
        callback_data=SelectTypePromoCode(type_promo=2)
    )
    kb.adjust(2)
    return kb.as_markup()


async def internal_squad_select(
    all_suad: GetAllInternalSquadsResponseDto,
    vds_id: int = None,
    protocol_id: int = None,
    lang: str = None,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for suad in all_suad.internal_squads:
        if vds_id is not None:
            data = SelectNewInSquad(
                uuid=str(suad.uuid), id_protocol=protocol_id
            )
        else:
            data = SelectInSquad(uuid=str(suad.uuid))
        kb.button(
            text=f'{suad.name} - 🏷 {len(suad.inbounds)}',
            callback_data=data
        )
    if vds_id is not None:
        kb.button(
            text=_('back_type_vpn', lang),
            callback_data=ProtocolList(vds_id=vds_id, protocol_id=protocol_id)
        )
    kb.adjust(1)
    return kb.as_markup()
