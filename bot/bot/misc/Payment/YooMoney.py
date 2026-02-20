import asyncio
import logging
import random
import uuid

from aiohttp import client_exceptions
from yoomoney_async import Quickpay, Client

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization

log = logging.getLogger(__name__)

_ = Localization.text


class YooMoney(PaymentSystem):
    CHECK_ID: str = None
    ID: str = None

    def __init__(
            self,
            session,
            config,
            message, user_id,
            price, month_count,
            type_pay, key_id,
            id_prot, id_loc,
            check_id=None
    ):
        super().__init__(
            session,
            message, user_id,
            type_pay, key_id,
            id_prot, id_loc,
            price, month_count
        )
        self.TOKEN = config.yoomoney_token
        self.TOKEN_WALLET = config.yoomoney_wallet_token

    async def create(self):
        self.ID = str(uuid.uuid4())

    async def check_payment(self):
        client = Client(self.TOKEN)
        tic = 0
        while tic < self.CHECK_PERIOD:
            try:
                history = await client.operation_history(label=self.ID)

                # history может быть dict или объектом
                if isinstance(history, dict):
                    operations = history.get("operations", [])
                else:
                    operations = getattr(history, "operations", [])

                for operation in operations:
                    # operation может быть dict или объектом
                    amount = operation["amount"] if isinstance(operation, dict) else operation.amount

                    cal_amount = self.price - self.price * 0.04
                    if amount < cal_amount:
                        continue

                    await self.successful_payment(self.price, 'YooMoney')
                    return

            except client_exceptions.ClientOSError:
                await asyncio.sleep(self.STEP + random.randint(0, 3))
                log.info('Error 104 YooMoney -- OK')
                continue

            except Exception as e:
                # чтобы не падало и не “съедало” кнопку молча
                log.error("YooMoney check_payment error", exc_info=e)

            tic += self.STEP
            await asyncio.sleep(self.STEP)

            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('YooMoney')

        return

    async def invoice(self):
        quick_pay = await Quickpay(
            receiver=self.TOKEN_WALLET,
            quickpay_form="shop",
            targets='Deposit balance',
            paymentType="SB",
            sum=self.price,
            label=self.ID
        ).start()
        return quick_pay.base_url

    async def to_pay(self):
        await self.create()
        link_invoice = await self.invoice()
        await self.pay_button(link_invoice)
        log.info(
            f'Create payment link YooMoney '
            f'User: {self.user_id} - {self.price} RUB'
        )
        try:
            await self.check_payment()
        except BaseException as e:
            log.error('The payment period has expired', exc_info=e)
        finally:
            await self.delete_pay_button('YooMoney')
            log.info('exit check payment YooMoney')

    def __str__(self):
        return 'Платежная система YooMoney'
