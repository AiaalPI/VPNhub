import asyncio
import logging
import uuid

from aiolava import LavaBusinessClient

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization

log = logging.getLogger(__name__)

_ = Localization.text


class Lava(PaymentSystem):
    CHECK_ID: str = None
    ID: str = None

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
        check_id=None
    ):
        super().__init__(
            session,
            message,
            user_id,
            type_pay,
            key_id,
            id_prot,
            id_loc,
            price,
            month_count
        )
        self.CHECK_ID = check_id
        self.CLIENT = LavaBusinessClient(
            private_key=config.lava_token_secret,
            shop_id=config.lava_id_project
        )

    async def create_id(self):
        self.ID = str(uuid.uuid4())

    async def create_invoice(self):
        invoice = await self.CLIENT.create_invoice(
            sum_=self.price,
            order_id=self.ID
        )
        return invoice

    async def check_payment(self):
        tic = 0
        while tic < self.CHECK_PERIOD:
            status = await self.CLIENT.check_invoice_status(order_id=self.ID)
            if status.data.status == 'success':
                await self.successful_payment(self.price, 'Lava')
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('Lava')
        return

    async def to_pay(self):
        await self.create_id()
        invoice = await self.create_invoice()
        await self.pay_button(invoice.data.url)
        log.info(
            f'Create payment link Lava '
            f'User: ID: {self.user_id}'
        )
        try:
            await self.check_payment()
        except BaseException as e:
            log.error(e, 'The payment period has expired')
        finally:
            await self.delete_pay_button('Lava')
            log.info('exit check payment Lava')

    def __str__(self):
        return 'Lava payment system'
