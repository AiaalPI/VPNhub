import asyncio
import logging
import uuid

from freekassa_ru import Freekassa

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization, get_lang

log = logging.getLogger(__name__)

_ = Localization.text


class FreeKassa(PaymentSystem):
    FK: Freekassa
    ID: str
    API_KEY: str = 'dfc1678b1494f88ecb729d3000a9ce05'
    SHOP_ID: str = '47359'

    def __init__(
        self,
        session,
        config,
        message,
        user_id,
        price,
        key_id,
        id_prot,
        id_loc,
        check_id=None
    ):
        super().__init__(
            session,
            message,
            user_id,
            key_id,
            id_prot,
            id_loc,
            price
        )
        self.FK = Freekassa(shop_id=self.SHOP_ID, api_key=self.API_KEY)

    async def create_id(self):
        self.ID = str(uuid.uuid4())

    async def create_invoice(self):
        payment_system_id = 42
        email = ''
        ip = ''
        amount = 300.00
        list_p = self.FK.create_order(payment_system_id, email, ip, amount)
        return list_p

    async def check_payment(self):
        tic = 0
        while tic < self.CHECK_PERIOD:

            await asyncio.sleep(self.STEP)
        return

    async def to_pay(self):
        await self.message.delete()
        await self.create_id()
        await self.create_invoice()

    def __str__(self):
        return 'FreeKassa payment system'
