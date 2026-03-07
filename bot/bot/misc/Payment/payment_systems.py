import logging

from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, Message
from aiogram.utils.formatting import Text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import (
    get_person,
    get_free_server_id,
    get_key_id,
    get_key_user,
    get_name_location_server
)
from bot.database.methods.insert import (
    add_payment,
    add_donate,
    add_key,
    add_referral_bonus,
)
from bot.database.methods.update import (
    add_time_key,
    update_switch_key,
    server_space_update,
    update_server_key, update_key_wg,
)
from bot.handlers.user.edit_or_get_key import get_img_type_vpn

from bot.keyboards.inline.user_inline import (
    pay_and_check,
    user_menu, instruction_manual
)
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.language import Localization, get_lang
from bot.misc.tariffs import get_paid_data_limit_gb
from bot.misc.util import CONFIG
from bot.service.create_file_str import str_to_file
from bot.service.edit_message import edit_message

log = logging.getLogger(__name__)

_ = Localization.text


class PaymentSystem:
    TOKEN: str
    CHECK_PERIOD = 50 * 60
    STEP = 5
    TIME_DELETE: int = 5 * 60
    TYPE_PAYMENT: str
    KEY_ID: int
    MESSAGE_ID_PAYMENT: Message = None
    session: AsyncSession = None

    def __init__(
            self,
            session,
            message,
            user_id,
            donate,
            key_id,
            id_prot,
            id_loc,
            price=None,
            month_count=None
    ):
        self.session = session
        self.message: Message = message
        self.user_id = user_id
        self.price = price
        self.month_count = month_count
        self.TYPE_PAYMENT = donate
        self.KEY_ID = key_id
        self.ID_PROT = id_prot
        self.ID_LOC = id_loc
        log.info(f'payment system: {self.TYPE_PAYMENT}')

    async def to_pay(self):
        raise NotImplementedError()

    async def pay_button(self, link_pay, delete=True, webapp=False):
        lang_user = await get_lang(self.session, self.user_id)
        if delete:
            try:
                await self.message.delete()
            except Exception:
                log.info('error delete message')
        self.MESSAGE_ID_PAYMENT = await self.message.answer_photo(
            photo=FSInputFile('bot/img/pay_subscribe.jpg'),
            caption=_('payment_balance_text', lang_user).format(price=self.price),
            reply_markup=await pay_and_check(link_pay, lang_user, webapp)
        )


    async def delete_pay_button(self, name_payment):
        if self.MESSAGE_ID_PAYMENT is not None:
            try:
                await self.message.bot.delete_message(
                    self.user_id,
                    self.MESSAGE_ID_PAYMENT.message_id
                )
                log.info(
                    f'user ID: {self.user_id}'
                    f' delete payment {self.price} RUB '
                    f'Payment - {name_payment}'
                )
            except Exception as e:
                log.error(
                    f'error delete pay button payment {name_payment}',
                    exc_info=e
                )
            finally:
                self.MESSAGE_ID_PAYMENT = None

    async def successful_payment(
        self, total_amount, name_payment, id_payment=None
    ):
        log.info(
            f'user ID: {self.user_id}'
            f' success payment {total_amount} RUB '
            f'Payment - {name_payment} '
            f'Type payment {self.TYPE_PAYMENT}'
        )
        lang_user = await get_lang(self.session, self.user_id)
        await add_payment(
            self.session,
            self.user_id,
            total_amount,
            name_payment,
            id_payment=id_payment,
            month_count=self.month_count
        )
        person = await get_person(self.session, self.user_id)
        await self._process_referral_cashback(person, id_payment)
        if self.TYPE_PAYMENT == CONFIG.type_payment.get(0):
            await self.message.answer(
                _('payment_success', lang_user)
                .format(total_month=self.month_count)
            )

            server = await get_free_server_id(
                self.session,
                self.ID_LOC,
                self.ID_PROT
            )
            if server is None:
                await add_key(
                    self.session,
                    person.tgid,
                    self.month_count * CONFIG.COUNT_SECOND_MOTH,
                    id_payment=id_payment,
                )
                await self.send_admin_new_pay(person)
                return
            key = await add_key(
                self.session,
                person.tgid,
                self.month_count * CONFIG.COUNT_SECOND_MOTH,
                id_payment=id_payment,
                server_id=server.id
            )
            try:
                download = await self.message.answer(
                    _('download', lang_user)
                )
                key = await get_key_id(self.session, key.id)
                server_manager = ServerManager(key.server_table)
                await server_manager.login()
                name_location = await get_name_location_server(
                    self.session,
                    key.server_table.id
                )
                if key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
                    config = await server_manager.get_key(
                        key.wg_public_key,
                        name_key=name_location,
                        key_id=key.id
                    )
                    await update_key_wg(
                        self.session, key.id, config.public_key
                    )
                else:
                    config = await server_manager.get_key(
                        self.user_id,
                        name_key=name_location,
                        key_id=key.id,
                        subscription_timestamp=key.subscription,
                        limit_gb=get_paid_data_limit_gb(self.month_count),
                    )
                server_parameters = await server_manager.get_all_user()

                await server_space_update(
                    self.session,
                    server.id,
                    len(server_parameters)
                )
            except Exception as e:
                await update_server_key(self.session, key.id)
                await self.message.answer(
                    _('server_not_connected', lang_user)
                )
                log.error('Error get config', exc_info=e)
                return
            await download.delete()
            await self.post_key(lang_user, key, config)
            await self.send_admin_new_pay(person)
        elif self.TYPE_PAYMENT == CONFIG.type_payment.get(1):
            await add_time_key(
                self.session,
                int(self.KEY_ID),
                self.month_count * CONFIG.COUNT_SECOND_MOTH,
                id_payment=id_payment
            )
            await self.message.answer(
                _('payment_success_extend', lang_user)
                .format(total_month=self.month_count)
            )
            text = Text(
                _('admin_message_payment_success', CONFIG.languages)
                .format(
                    username=person.username,
                    user_id=self.user_id,
                    month_count=self.month_count,
                    price=self.price
                )
            )
            await self.message.bot.send_message(
                CONFIG.admin_tg_id,
                **text.as_kwargs()
            )
            await self.message.answer_photo(
                photo=FSInputFile('bot/img/main_menu.jpg'),
                reply_markup=await user_menu(lang_user, person.tgid)
            )
            return
        elif self.TYPE_PAYMENT == CONFIG.type_payment.get(2):
            await add_donate(self.session, person.username, self.price)
            await self.message.answer(
                _('donate_successful', lang_user)
            )
            text = Text(
                _('admin_message_payment_success_donate', CONFIG.languages)
                .format(
                    username=person.username,
                    user_id=self.user_id,
                    price=self.price
                )
            )
            await self.message.bot.send_message(
                CONFIG.admin_tg_id,
                **text.as_kwargs()
            )
            await self.message.answer_photo(
                photo=FSInputFile('bot/img/main_menu.jpg'),
                reply_markup=await user_menu(lang_user, person.tgid)
            )
            return
        elif self.TYPE_PAYMENT == CONFIG.type_payment.get(3):
            await update_switch_key(self.session, self.KEY_ID, True)
            await self.message.answer(
                _('payment_success_switch', lang_user),
            )
            text = Text(
                _('admin_message_payment_success_switch', CONFIG.languages)
                .format(
                    username=person.username,
                    user_id=self.user_id,
                    price=self.price
                )
            )
            await self.message.bot.send_message(
                CONFIG.admin_tg_id,
                **text.as_kwargs()
            )
            return
        else:
            log.error(f'type payment {self.TYPE_PAYMENT} not found')
            await self.message.bot.send_message(
                self.user_id,
                _('error_send_admin', lang_user)
            )
            return
    async def _process_referral_cashback(self, person, payment_id: str | None):
        if person is None or person.referral_user_tgid is None:
            return
        referrer_id = int(person.referral_user_tgid)
        if referrer_id == int(self.user_id):
            return
        bonus_days = 3
        bonus_seconds = bonus_days * 24 * 60 * 60
        try:
            ref_keys = await get_key_user(self.session, referrer_id)
            if not ref_keys:
                return
            # Extend the key with the latest expiry to maximize bonus usefulness.
            best_key = max(ref_keys, key=lambda key: int(key.subscription or 0))
            await add_time_key(
                self.session,
                best_key.id,
                bonus_seconds,
                id_payment=payment_id
            )
            await add_referral_bonus(
                self.session,
                referrer_id=referrer_id,
                referee_id=self.user_id,
                bonus_days=bonus_days,
                payment_id=payment_id
            )
            ref_lang = await get_lang(self.session, referrer_id)
            friend_name = person.fullname or person.username or str(self.user_id)
            await self.message.bot.send_message(
                referrer_id,
                _('referral_friend_paid_bonus', ref_lang).format(
                    name=friend_name,
                    days=bonus_days
                ),
            )
        except Exception:
            log.exception(
                'event=referral_cashback status=failed referrer_id=%s referee_id=%s',
                referrer_id,
                self.user_id
            )

    async def send_admin_new_pay(self, person):
        text = Text(
            _('admin_message_payment_success', CONFIG.languages)
            .format(
                username=person.username,
                user_id=self.user_id,
                month_count=self.month_count,
                price=self.price
            )
        )
        await self.message.bot.send_message(
            CONFIG.admin_tg_id,
            **text.as_kwargs()
        )

    async def post_key(self, lang, key, config):
        photo = await get_img_type_vpn(key)
        if (
            key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value
            or key.server_table.type_vpn == CONFIG.TypeVpn.AMNEZIA_WG.value
        ):
            file_name = f'{key.user_tgid}.conf'
            if key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
                caption = _('how_to_connect_wg', lang).format(
                    name_vpn=ServerManager.VPN_TYPES.get(
                        key.server_table.type_vpn
                    ).NAME_VPN
                )
                text = config.key
            else:
                caption = _('how_to_connect', lang).format(
                    name_vpn=ServerManager.VPN_TYPES.get(
                        key.server_table.type_vpn)
                    .NAME_VPN,
                    config=config.get('config')
                )
                text = config.get('config')
            await self.message.answer_document(
                document=await str_to_file(
                    file_name=file_name,
                    text=text
                ),
                caption=caption,
                reply_markup=await instruction_manual(
                    lang,
                    key.server_table.type_vpn
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        elif key.server_table.type_vpn == CONFIG.TypeVpn.REMNAWAVE.value:
            connect_message = _('how_to_connect_remnawave', lang).format(
                config=config,
            )
            await edit_message(
                self.message,
                photo=photo,
                caption=connect_message,
                reply_markup=await instruction_manual(
                    lang,
                    key.server_table.type_vpn,
                    link_sub=config
                )
            )
        elif key.server_table.type_vpn == CONFIG.TypeVpn.MARZBAN.value:
            connect_message = _('how_to_connect_marzban', lang).format(
                config=config,
            )
            await edit_message(
                self.message,
                photo=photo,
                caption=connect_message,
                reply_markup=await instruction_manual(
                    lang,
                    key.server_table.type_vpn,
                    link_sub=config
                )
            )
        else:
            connect_message = _('how_to_connect', lang).format(
                name_vpn=ServerManager.VPN_TYPES.get(key.server_table.type_vpn)
                .NAME_VPN,
                config=config,
            )
            await edit_message(
                self.message,
                photo=photo,
                caption=connect_message,
                reply_markup=await instruction_manual(
                    lang,
                    key.server_table.type_vpn
                ),
                parse_mode=ParseMode.MARKDOWN
            )
