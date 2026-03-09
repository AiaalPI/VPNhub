import asyncio
import aiohttp
import logging
import random
import uuid

from yoomoney_async import Quickpay

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization, get_lang

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
        headers = {"Authorization": f"Bearer {self.TOKEN}"}
        tic = 0
        while tic < self.CHECK_PERIOD:
            try:
                async with aiohttp.ClientSession() as http:
                    async with http.post(
                        "https://yoomoney.ru/api/operation-history",
                        headers=headers,
                        data={"label": self.ID, "records": 10}
                    ) as resp:
                        data = await resp.json(content_type=None)
                        log.info(f"YooMoney poll: {data}")
                        for op in data.get("operations", []):
                            amount = float(op.get("amount", 0))
                            cal_amount = self.price - self.price * 0.04
                            if amount >= cal_amount:
                                await self.successful_payment(
                                    self.price, 'YooMoney'
                                )
                                return
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error(f"YooMoney check error: {e}", exc_info=True)
            tic += self.STEP
            await asyncio.sleep(self.STEP)
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
        try:
            link_invoice = await self.invoice()
        except Exception as e:
            log.error('YooMoney: failed to create invoice', exc_info=e)
            lang_user = await get_lang(self.session, self.user_id)
            await self.message.answer(_('error_send_admin', lang_user))
            return
        await self.pay_button(link_invoice)
        log.info(
            f'Create payment link YooMoney '
            f'User: {self.user_id} - {self.price} RUB'
        )
        try:
            await self.check_payment()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error('YooMoney: check_payment error', exc_info=e)
        finally:
            await self.delete_pay_button('YooMoney')
            log.info('exit check payment YooMoney')

    def __str__(self):
        return 'Платежная система YooMoney'
