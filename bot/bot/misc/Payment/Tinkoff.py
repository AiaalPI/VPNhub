import asyncio
import logging
import uuid

from tinkoff_acquiring import TinkoffAcquiringAPIClient

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import get_lang, Localization

log = logging.getLogger(__name__)

_ = Localization.text


class TinkoffPay(PaymentSystem):

    CLIENT: TinkoffAcquiringAPIClient

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
        self.CLIENT = TinkoffAcquiringAPIClient(
            config.tinkoff_terminal_key, config.tinkoff_secret
        )

    async def new_order(self, lang_user):
        return await self.CLIENT.init_payment(
            amount=float(self.price),
            order_id=str(uuid.uuid4()),
            description=_('description_payment', lang_user),
        )

    async def check_pay_wallet(self, payment_id):
        tic = 0
        while tic < self.CHECK_PERIOD:
            order_preview = await self.CLIENT.get_payment_state(payment_id)
            if order_preview['Status'] == "CONFIRMED":
                await self.successful_payment(
                    self.price,
                    'TinkoffPay'
                )
                return
            tic += self.STEP
            await asyncio.sleep(self.STEP)
            if self.CHECK_PERIOD - tic <= self.TIME_DELETE:
                await self.delete_pay_button('TinkoffPay')
        return

    async def to_pay(self):
        lang_user = await get_lang(self.session, self.user_id)
        response = await self.new_order(lang_user)
        payment_id = response['PaymentId']
        link_pay = response['PaymentURL']
        await self.pay_button(link_pay)
        log.info(
            f'Create payment link TinkoffPay '
            f'User: ID: {self.user_id}'
        )
        try:
            await self.check_pay_wallet(payment_id)
        except BaseException as e:
            log.error(e, 'The payment period has expired')
        finally:
            await self.delete_pay_button('TinkoffPay')
            log.info('exit check payment TinkoffPay')

    def __str__(self):
        return 'Платежная система TinkoffPay'
