import asyncio
import logging

from aiocryptopay import AioCryptoPay, Networks
from aiocryptopay.base import BaseClient

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization

log = logging.getLogger(__name__)

_ = Localization.text


class CryptoBot(PaymentSystem):
    CRYPTO: type(AioCryptoPay)

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
        self.CRYPTO = AioCryptoPay(
            token=config.crypto_bot_api,
            network=Networks.MAIN_NET
        )

    async def check_pay_wallet(self, order):
        tic = 0
        while tic < self.CHECK_PERIOD:
            order_preview = await self.CRYPTO.get_invoices(
                invoice_ids=order.invoice_id
            )
            if order_preview.status == "paid":
                await self.successful_payment(
                    self.price,
                    'CryptoBot'
                )
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('CryptoBot')
        await self.CRYPTO.delete_invoice(
            invoice_id=order.invoice_id
        )
        return

    async def to_pay(self):
        order = await self.CRYPTO.create_invoice(
            amount=self.price,
            fiat='RUB',
            currency_type='fiat'
        )
        await self.pay_button(order.mini_app_invoice_url, webapp=False)
        log.info(
            f'Create payment link CryptoBot '
            f'User: ID: {self.user_id}'
        )
        try:
            await self.check_pay_wallet(order)
        except BaseException as e:
            log.error(e, 'The payment period has expired')
        finally:
            await self.delete_pay_button('CryptoBot')
            await self.CRYPTO.close()
            log.info('exit check payment CryptoBot')

    def __str__(self):
        return 'Платежная система CryptoBot'
