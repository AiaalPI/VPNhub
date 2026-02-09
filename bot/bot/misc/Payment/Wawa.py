import asyncio
import decimal
import logging
import uuid



from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.Payment.wata import PaymentClient
from bot.misc.language import Localization, get_lang

log = logging.getLogger(__name__)

_ = Localization.text


class Wawa(PaymentSystem):
    CLIENT: PaymentClient
    TOKEN: str
    BASE_URL: str = 'https://api.wata.pro'
    ID: str
    STEP = 30

    def __init__(
        self,
        session,
        config,
        message, user_id,
        price, month_count,
        type_pay, key_id,
        id_prot, id_loc,
        data=None
    ):
        super().__init__(
            session,
            message, user_id,
            type_pay, key_id,
            id_prot, id_loc,
            price, month_count
        )
        self.TOKEN = config.wawa_token_card

    async def create_id(self):
        self.ID = str(uuid.uuid4())

    async def create_invoice(self, lang, client):
        bot = await self.message.bot.me()
        await self.create_id()
        return await client.payment.create(
            amount=decimal.Decimal(self.price),
            currency="RUB",
            description=_('description_payment', lang),
            order_id=
            f'{self.month_count}'
            f'/{self.TYPE_PAYMENT}'
            f'/{self.KEY_ID}'
            f'/{self.ID_PROT}'
            f'/{self.ID_LOC}'
            f'/{self.message.message_id}'
            f'/{self.user_id}',
            success_redirect_url=f'https://t.me/{bot.username}',
            fail_redirect_url=f'https://t.me/{bot.username}'
        )

    async def to_pay(self):
        client = PaymentClient.initialize(
            api_key=self.TOKEN,
            base_url=self.BASE_URL,
        )
        client.__init__(
            api_key=self.TOKEN,
            base_url=self.BASE_URL,
            parent_logger_name='wata',
            base_logger_name='wata',
            log_level=logging.ERROR
        )
        lang_user = await get_lang(self.session, self.user_id)
        payment = await self.create_invoice(lang_user, client)
        await client.close()
        await self.pay_button(payment['url'], webapp=False)
        log.info(
            f'Create payment link Wawa '
            f'User: ID: {self.user_id}'
        )

    def __str__(self):
        return 'Платежная система Wata'



class WawaSpb(Wawa):

    def __init__(
        self,
        session,
        config,
        message, user_id,
        price, month_count,
        type_pay, key_id,
        id_prot, id_loc,
        data=None
    ):
        super().__init__(
            session,
            config,
            message, user_id,
            price, month_count,
            type_pay, key_id,
            id_prot, id_loc,
            data=None
        )
        self.TOKEN = config.wawa_token_sbp


class WawaVisa(Wawa):

    def __init__(
        self,
        session,
        config,
        message, user_id,
        price, month_count,
        type_pay, key_id,
        id_prot, id_loc,
        data=None
    ):
        super().__init__(
            session,
            config,
            message, user_id,
            price, month_count,
            type_pay, key_id,
            id_prot, id_loc,
            data=None
        )
        self.TOKEN = config.wawa_token_visa


