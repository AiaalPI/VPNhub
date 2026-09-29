import logging
from urllib.parse import urlencode

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.services.bot_payment_orders import create_order

log = logging.getLogger(__name__)


class YooMoney(PaymentSystem):
    def __init__(self, session, config, message, user_id, price, month_count,
                 type_pay, key_id, id_prot, id_loc, check_id=None):
        super().__init__(session, message, user_id, type_pay, key_id, id_prot,
                         id_loc, price, month_count)
        self.TOKEN_WALLET = config.yoomoney_wallet_token
        self.ID = None

    async def create(self):
        # Persist before exposing a payable URL. A process restart cannot lose it.
        order = await create_order(self)
        self.ID = order.id

    async def invoice(self):
        return 'https://yoomoney.ru/quickpay/confirm?' + urlencode({
            'receiver': self.TOKEN_WALLET, 'quickpay-form': 'button',
            'paymentType': 'AC', 'sum': f'{self.price:.2f}', 'label': self.ID,
        })

    async def to_pay(self):
        await self.create()
        await self.pay_button(await self.invoice())
        # The persistent scheduler checks receipts and retries provisioning.
        # An unpaid invoice is not an error and does not need admin moderation.
        log.info('event=yoomoney.invoice_created order=%s', self.ID)
