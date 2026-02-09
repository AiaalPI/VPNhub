import logging

from aiogram import F, Router
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline.user_inline import pay_stars
from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import get_lang, Localization
from bot.misc.util import CONFIG

stars_router = Router()
log = logging.getLogger(__name__)

_ = Localization.text


class Stars(PaymentSystem):

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
        self.TOKEN = config.token_stars


    async def rub_to_stars(self) -> int:
        price_to_stars = [
            (176.99, 100),
            (256.99, 150),
            (419.00, 250),
            (579.00, 350),
            (819.00, 500),
            (1229.00, 750),
            (1629.00, 1000),
            (2429.00, 1500),
            (4039.00, 2500),
            (8099.00, 5000),
            (15999.00, 10000),
            (40299.00, 25000),
            (80999.00, 50000),
            (159999.00, 100000),
            (239999.00, 150000)
        ]

        if self.price <= price_to_stars[0][0]:
            return round(
                price_to_stars[0][1] * (self.price / price_to_stars[0][0])
            )
        for i in range(1, len(price_to_stars)):
            lower_price, lower_stars = price_to_stars[i - 1]
            upper_price, upper_stars = price_to_stars[i]
            if lower_price <= self.price <= upper_price:
                ratio = (self.price - lower_price) / (upper_price - lower_price)
                stars = lower_stars + ratio * (upper_stars - lower_stars)
                return round(stars)
        last_price, last_stars = price_to_stars[-2]
        max_price, max_stars = price_to_stars[-1]
        ratio = (self.price - max_price) / (max_price - last_price)
        stars = max_stars + ratio * (max_stars - last_stars)
        return round(stars)

    async def to_pay(self):
        await self.message.delete()
        lang_user = await get_lang(self.session, self.user_id)
        amount = await self.rub_to_stars()
        title = _('description_payment', lang_user)
        description = (
            _('payment_balance_text2', lang_user).format(price=self.price)
        )
        prices = [LabeledPrice(label="XTR", amount=amount)]
        await self.message.answer_invoice(
            title=title,
            description=description,
            prices=prices,
            provider_token=self.TOKEN,
            payload=
            f'{self.price}'
            f':{self.month_count}'
            f':{self.TYPE_PAYMENT}'
            f':{self.KEY_ID}'
            f':{self.ID_PROT}'
            f':{self.ID_LOC}',
            currency="XTR",
            reply_markup=await pay_stars(lang_user)
        )
        log.info(
            f'Create payment Stars '
            f'User: ID: {self.user_id}'
        )
        return self.price

    def __str__(self):
        return 'Платежная система Telegram Stars'


@stars_router.pre_checkout_query()
async def on_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@stars_router.message(F.successful_payment)
async def on_successful_payment(message: Message, session: AsyncSession):
    data = message.successful_payment.invoice_payload.split(':')
    price = int(data[0])
    donate = CONFIG.type_payment.get(2) == data[2]
    if not donate:
        month_count = int(data[1])
    else:
        month_count = 1
    key_id = int(data[3])
    id_prot = int(data[4])
    id_loc = int(data[5])
    payment_system = PaymentSystem(
        session=session,
        message=message,
        user_id=message.from_user.id,
        donate=data[2],
        price=price,
        month_count=month_count,
        id_prot=id_prot,
        id_loc=id_loc,
        key_id=key_id
    )
    try:
        await payment_system.successful_payment(price, 'Telegram Stars')
    except BaseException as e:
        log.error('The payment period has expired', exc_info=e)
    finally:
        log.info('exit check payment Stars')

