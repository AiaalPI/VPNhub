from aiogram.filters.callback_data import CallbackData


class ChoosingMonths(CallbackData, prefix='month'):
    price: int
    month_count: int
    type_pay: str
    key_id: int
    id_prot: int
    id_loc: int


class TrialPeriod(CallbackData, prefix='trial_period'):
    id_prot: int
    id_loc: int


class ChoosingPyment(CallbackData, prefix='payment'):
    payment: str


class CheckPayment(CallbackData, prefix='c'):
    payment_id: str
    payment_price: int
    id_message: int
    payment: str


class ChoosingPrise(CallbackData, prefix='price'):
    price: int
    payment: str
    type_pay: str
    key_id: int
    month_count: int
    id_prot: int
    id_loc: int


class ChoosingVPN(CallbackData, prefix='VPN_type'):
    type: int


class ChoosingConnectionMethod(CallbackData, prefix='connect'):
    connection: bool


class ChoosingPanel(CallbackData, prefix='panel'):
    panel: str


class ServerWork(CallbackData, prefix='server_work'):
    work: bool
    id_protocol: int


class ServerAutoWork(CallbackData, prefix='server_auto_work'):
    work: bool
    id_protocol: int


class ServerUserList(CallbackData, prefix='server_list'):
    action: bool
    id_protocol: int


class ServerSwitchPay(CallbackData, prefix='location_switch_pay'):
    id_location: int
    action: bool


class ServerDelete(CallbackData, prefix='server_delete'):
    id_protocol: int


class EditUserPanel(CallbackData, prefix='edit_user'):
    action: str


class DeleteTimeClient(CallbackData, prefix='delete_time'):
    delete_time: bool


class DeleteStaticUser(CallbackData, prefix='delete_static_user'):
    name: str
    protocol_id: int


class MissingMessage(CallbackData, prefix='missing_user'):
    option: str


class PromocodeDelete(CallbackData, prefix='delete_promo'):
    id_promo: int
    mes_id: int


class PromoCodeChoosing(CallbackData, prefix='promo_choosing'):
    id_promo: int
    percent: int
    price: int
    type_pay: str
    key_id: int
    id_prot: int
    id_loc: int
    month_count: int


class AplicationReferral(CallbackData, prefix='app_referral'):
    type: bool


class ApplicationSuccess(CallbackData, prefix='app_referral_id'):
    id_application: int
    mes_id: int


class ChooseLocation(CallbackData, prefix='choose_server'):
    id_location: int
    key_id: int
    type_vpn: int
    payment: bool


class BackTypeVpn(CallbackData, prefix='back_type_vpn'):
    key_id: int


class MessageAdminUser(CallbackData, prefix='message_admin_user'):
    id_user: int


class EditKeysUser(CallbackData, prefix='edit_keys_user'):
    id_user: int


class BlockedUserPanel(CallbackData, prefix='blocked_user'):
    action: str
    id_user: int


class ChoosingLang(CallbackData, prefix='language'):
    lang: str


class GroupAction(CallbackData, prefix='group_action'):
    action: str


class ChooseTypeVpn(CallbackData, prefix='choose_type_vpn'):
    type_vpn: int
    key_id: int
    payment: bool


class ChooseTypeVpnHelp(CallbackData, prefix='choose_type_help_vpn'):
    type_vpn: int


class ConnectMenu(CallbackData, prefix='connect_menu'):
    action: str


class DonatePrice(CallbackData, prefix='donate_price'):
    price: int


class EditKey(CallbackData, prefix='edit_key'):
    key_id: int


class DetailKey(CallbackData, prefix='detail_key'):
    key_id: int


class ShowKey(CallbackData, prefix='show_key_user'):
    key_id: int


class ExtendKey(CallbackData, prefix='extend_key'):
    key_id: int


class AutoPay(CallbackData, prefix='auto_pay'):
    work: bool


class ReferralKeys(CallbackData, prefix='referral_keys'):
    key_id: int
    add_day: int


class Instructions(CallbackData, prefix='instructions'):
    type_device: str


class EditKeysAdmin(CallbackData, prefix='edit_keys_admin'):
    action: str
    id_user: int


class ButtonsMailing(CallbackData, prefix='buttons_mailing'):
    action: str


class EditLocations(CallbackData, prefix='edit_locations'):
    action: str
    id: int


class Locations(CallbackData, prefix='locations'):
    id: int


class ChooseLocations(CallbackData, prefix='choose_locations'):
    id: int


class VdsList(CallbackData, prefix='vds_list'):
    location_id: int
    vds_id: int

class ChooseVdsList(CallbackData, prefix='choose_vds_list'):
    location_id: int
    vds_id: int


class AddVds(CallbackData, prefix='add_vds'):
    location_id: int


class EditVds(CallbackData, prefix='edit_vds'):
    action: str
    id: int


class AddProtocol(CallbackData, prefix='add_protocol'):
    vds_id: int


class ProtocolList(CallbackData, prefix='protocol_list'):
    vds_id: int
    protocol_id: int


class ChooseProtocolList(CallbackData, prefix='choose_protocol_list'):
    vds_id: int
    protocol_id: int


class ChoosingTypeServer(CallbackData, prefix='type_server'):
    type_server: bool


class ShowMetric(CallbackData, prefix='show_metric'):
    id_metric: int


class RemoveMetric(CallbackData, prefix='remove_metric'):
    id_metric: int


class StatusUserPanel(CallbackData, prefix='status_user'):
    status: bool
    id_user: int


class SelectTypePromoCode(CallbackData, prefix='select_type_promo_code'):
    type_promo: int


class SelectInSquad(CallbackData, prefix='select_in_squad'):
    uuid: str


class SelectNewInSquad(CallbackData, prefix='select_new_in_squad'):
    uuid: str
    id_protocol: int


class EditInSquad(CallbackData, prefix='edit_in_squad'):
    id_protocol: int


class ShowUserDevices(CallbackData, prefix='show_user_devices'):
    key_id: int


class RemoveUserDevices(CallbackData, prefix='remove_user_devices'):
    key_id: int
    hwid: str
