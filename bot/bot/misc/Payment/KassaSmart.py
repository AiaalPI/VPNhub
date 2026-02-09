import asyncio
import logging
import uuid
from typing import Self

from async_yookassa import Configuration, Payment
from async_yookassa.models.payment_request import PaymentRequest
from pydantic import model_validator

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization, get_lang

log = logging.getLogger(__name__)

_ = Localization.text


class KassaSmart(PaymentSystem):
    CHECK_ID: str = None
    ID: str = None
    EMAIL: str

    def __init__(
        self,
        session,
        config,
        message,
        user_id,
        price,
        month_count,
        type_pay,
        key_id,
        id_prot,
        id_loc,
        data=None
    ):
        super().__init__(
            session,
            message, user_id,
            type_pay, key_id,
            id_prot, id_loc,
            price, month_count
        )
        self.ACCOUNT_ID = int(config.yookassa_shop_id)
        self.SECRET_KEY = config.yookassa_secret_key

    async def create(self):
        self.ID = str(uuid.uuid4())

    async def check_payment(self):
        Configuration.account_id = self.ACCOUNT_ID
        Configuration.secret_key = self.SECRET_KEY
        tic = 0
        while tic < self.CHECK_PERIOD:
            res = await Payment.find_one(self.ID)
            if res.status == 'succeeded':
                await self.successful_payment(
                    self.price,
                    'YooKassaSmart',
                    id_payment=self.ID
                )
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('YooKassaSmart')
        return

    async def invoice(self, lang_user):
        bot = await self.message.bot.me()
        data = {
            "amount": {
                "value": self.price,
                "currency": "RUB"
            },
            "need_email": True,
            "send_email_to_provider": True,
            "receipt": {
                "customer": {
                    "full_name": self.message.from_user.full_name,
                    "email": 'admin@gmail.com',
                },
                "items": [
                    {
                        "description": _('description_payment', lang_user),
                        "quantity": "1.00",
                        "amount": {
                            "value": self.price,
                            "currency": "RUB"
                        },
                        "vat_code": "2",
                        "payment_mode": "full_payment",
                        "payment_subject": "commodity"
                    },
                ]
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f'https://t.me/{bot.username}'
            },
            "capture": True,
            "description": _('description_payment', lang_user),
        }
        params_object = KassaPaymentRequest(**data)
        payment = await Payment.create(params_object, self.ID)
        self.ID = payment.id
        return payment.confirmation.confirmation_url
    @staticmethod
    async def auto_payment(
            config,
            lang_user,
            payment_id,
            price,
    ):
        try:
            Configuration.account_id = config.yookassa_shop_id
            Configuration.secret_key = config.yookassa_secret_key
            payment = await Payment.create({
                "amount": {
                    "value": price,
                    "currency": "RUB"
                },
                "capture": True,
                "description": _('description_payment', lang_user),
                "payment_method_id": payment_id
            })
            tic = 0
            while tic < 60:
                res = await Payment.find_one(payment.id)
                if res.status == 'succeeded':
                    return res
                tic += 2
                await asyncio.sleep(2)
            return None
        except Exception as e:
            log.error(
                f'Error Auto Pay KassaSmart, ID payment {payment_id}',
                exc_info=e
            )
            return None

    async def to_pay(self):
        await self.message.delete()
        await self.create()
        Configuration.account_id = self.ACCOUNT_ID
        Configuration.secret_key = self.SECRET_KEY
        lang_user = await get_lang(self.session, self.user_id)
        link_invoice = await self.invoice(lang_user)
        await self.pay_button(link_invoice, delete=False)
        log.info(
            f'Create payment link YooKassaSmart '
            f'User: (ID: {self.user_id}'
        )
        try:
            await self.check_payment()
        except BaseException as e:
            log.error('The payment period has expired', exc_info=e)
        finally:
            await self.delete_pay_button('YooKassaSmart')
            log.info('exit check payment YooKassaSmart')

    def __str__(self):
        return 'YooKassaSmart payment system'


class KassaPaymentRequest(PaymentRequest):

    @model_validator(mode="after")
    def validate_data(self, values: Self):
        return self
