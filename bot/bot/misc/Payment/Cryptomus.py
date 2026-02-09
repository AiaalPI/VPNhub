import asyncio
import logging
import uuid

from cryptomus import Client
from cryptomus.payments import Payment
from cryptomus.payouts import Payout

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization

log = logging.getLogger(__name__)

_ = Localization.text


class Cryptomus(PaymentSystem):
    PAYMENT: Payment
    ID: str

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
        self.PAYMENT = Client.payment(
            config.cryptomus_key,
            config.cryptomus_uuid
        )
        #self.PAYMENT.requestBuilder.api_url='https://api.heleket.com/'

    async def create_id(self):
        self.ID = str(uuid.uuid4())

    async def new_payment(self):
        return {
            'amount': str(self.price),
            'currency': 'RUB',
            'order_id': self.ID,
            'lifetime': self.CHECK_PERIOD - 30,
        }

    async def check_pay_wallet(self, uuid_order):
        tic = 0
        while tic < self.CHECK_PERIOD:
            order_info = self.PAYMENT.info(
                {'uuid': uuid_order}
            )
            if order_info['status'] == "paid":
                await self.successful_payment(
                    self.price,
                    'Cryptomus'
                )
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('Cryptomus')
        return

    async def to_pay(self):
        await self.create_id()
        data = await self.new_payment()
        result = self.PAYMENT.create(data)
        await self.pay_button(result['url'])
        log.info(
            f'Create payment link Cryptomus '
            f'User: ID: {self.user_id}'
        )
        try:
            await self.check_pay_wallet(result['uuid'])
        except BaseException as e:
            log.error(e, 'The payment period has expired')
        finally:
            await self.delete_pay_button('Cryptomus')
            log.info('exit check payment Cryptomus')

    def __str__(self):
        return 'Платежная система Cryptomus'


class Heleket(PaymentSystem):
    PAYMENT: Payment
    ID: str

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
        self.PAYMENT = Client.payment(
            config.heleket_key,
            config.heleket_uuid
        )
        self.PAYMENT.requestBuilder.api_url='https://api.heleket.com/'

    async def create_id(self):
        self.ID = str(uuid.uuid4())

    async def new_payment(self):
        return {
            'amount': str(self.price),
            'currency': 'RUB',
            'order_id': self.ID,
            'lifetime': self.CHECK_PERIOD - 30,
        }

    async def check_pay_wallet(self, uuid_order):
        tic = 0
        while tic < self.CHECK_PERIOD:
            order_info = self.PAYMENT.info(
                {'uuid': uuid_order}
            )
            if order_info['status'] == "paid":
                await self.successful_payment(
                    self.price,
                    'Heleket'
                )
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('Heleket')
        return

    async def to_pay(self):
        await self.create_id()
        data = await self.new_payment()
        result = self.PAYMENT.create(data)
        await self.pay_button(result['url'])
        log.info(
            f'Create payment link Heleket '
            f'User: ID: {self.user_id}'
        )
        try:
            await self.check_pay_wallet(result['uuid'])
        except BaseException as e:
            log.error('The payment period has expired', exc_info=e)
        finally:
            await self.delete_pay_button('Heleket')
            log.info('exit check payment Heleket')

    def __str__(self):
        return 'Платежная система Heleket'
