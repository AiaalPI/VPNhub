import ipaddress
import logging
from http import HTTPStatus

from aiogram import Bot
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.Payment.wata.modules import WebhookModule
from bot.misc.util import CONFIG
from bot.webhooks.util import get_message

log = logging.getLogger(__name__)

wata_router = APIRouter()


@wata_router.post("/payments/wata/webhook")
async def wata_webhook(request: Request):
    session: AsyncSession = request.state.session
    bot: Bot = request.state.bot
    signature = request.headers.get("X-Signature")
    raw_body = await request.body()
    try:
        wh_module = WebhookModule(http_client=request.app.state.http_client)
        data = await wh_module.process_webhook(
            signature=signature, data=raw_body
        )
        if data is None:
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)

        status = data.get('transactionStatus')
        if status != 'Paid':
            log.info(f'Not Paid wata notification: {data}')
            return Response(status_code=HTTPStatus.OK)

        log.info(f'success payment wata notification: {data}')
        order_id = data.get('orderId')
        if order_id is None:
            raise Exception(f"Order ID Wata not found: {order_id}")
        order_id = order_id.split('/')
        donate = CONFIG.type_payment.get(2) == order_id[1]
        if not donate:
            month_count = int(order_id[0])
        else:
            month_count = 1
        key_id = int(order_id[2])
        id_prot = int(order_id[3])
        id_loc = int(order_id[4])
        id_user = int(order_id[6])
        try:
            message_id = order_id[5]
        except IndexError:
            message_id = 1
        price_str = data.get('amount')
        price = int(float(price_str))
        message = await get_message(bot, id_user, message_id)
        payment_system = PaymentSystem(
            session=session,
            message=message,
            user_id=id_user,
            donate=order_id[1],
            price=price,
            month_count=month_count,
            id_prot=id_prot,
            id_loc=id_loc,
            key_id=key_id
        )
        try:
            await payment_system.successful_payment(
                price,
                'Wata'
            )
        except BaseException as e:
            log.error('Error wata successful payment', exc_info=e)
    except Exception as e:
        log.error('Error wata when processing the notification:', exc_info=e)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST)
    return Response(status_code=HTTPStatus.OK)
