import asyncio
import aiohttp
import json
import logging
import random
import uuid
from urllib.parse import urlencode, quote
from aiohttp import client_exceptions

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.language import Localization, get_lang
from bot.misc.util import CONFIG

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
        headers = {
            "Authorization": f"Bearer {self.TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        tic = 0
        while tic < self.CHECK_PERIOD:
            try:
                async with aiohttp.ClientSession() as http:
                    async with http.post(
                        "https://yoomoney.ru/api/operation-history",
                        headers=headers,
                        data={"label": self.ID, "records": 10}
                    ) as resp:
                        raw_text = await resp.text()
                        log.info(
                            "YooMoney poll status=%s content_type=%s body=%s",
                            resp.status,
                            resp.headers.get("Content-Type"),
                            raw_text[:500],
                        )
                        if resp.status in (401, 403):
                            log.error(
                                "YooMoney auth failed status=%s www_authenticate=%s body=%s",
                                resp.status,
                                resp.headers.get("WWW-Authenticate"),
                                raw_text[:500],
                            )
                            return False
                        if resp.status >= 400:
                            log.error(
                                "YooMoney poll http_error status=%s body=%s",
                                resp.status,
                                raw_text[:500],
                            )
                            return False
                        try:
                            data = json.loads(raw_text) if raw_text else {}
                        except json.JSONDecodeError:
                            log.warning(
                                "YooMoney poll non-json body=%s",
                                raw_text[:500],
                            )
                            continue
                        if isinstance(data, str):
                            try:
                                data = json.loads(data)
                            except json.JSONDecodeError:
                                log.warning(
                                    "YooMoney poll json-string body=%s",
                                    data[:500],
                                )
                                continue
                        if not isinstance(data, dict):
                            log.warning(
                                "YooMoney poll unexpected payload type=%s",
                                type(data).__name__,
                            )
                            continue
                        operations = data.get("operations", [])
                        if not isinstance(operations, list):
                            log.warning(
                                "YooMoney poll invalid operations type=%s",
                                type(operations).__name__,
                            )
                            continue
                        for op in operations:
                            if not isinstance(op, dict):
                                continue
                            amount = float(op.get("amount", 0))
                            cal_amount = self.price - self.price * 0.04
                            if amount >= cal_amount:
                                await self.successful_payment(
                                    self.price, 'YooMoney'
                                )
                                return True
            except asyncio.CancelledError:
                raise
            except client_exceptions.ConnectionTimeoutError as e:
                log.error("YooMoney check timeout: %s", e, exc_info=True)
                return False
            except client_exceptions.ClientError as e:
                log.error("YooMoney check client error: %s", e, exc_info=True)
                return False
            except Exception as e:
                log.error(f"YooMoney check error: {e}", exc_info=True)
                return False
            tic += self.STEP
            await asyncio.sleep(self.STEP)
        return False

    async def invoice(self):
        params = {
            "receiver": self.TOKEN_WALLET,
            "quickpay-form": "shop",
            "targets": "Deposit balance",
            "paymentType": "SB",
            "sum": self.price,
            "label": self.ID,
        }
        query = urlencode(params, quote_via=quote)
        return f"https://yoomoney.ru/quickpay/confirm.xml?{query}"

    async def to_pay(self):
        await self.create()
        log.info(
            "YooMoney: start creating invoice user_id=%s price=%s label=%s",
            self.user_id,
            self.price,
            self.ID,
        )
        try:
            link_invoice = await self.invoice()
            log.info(
                "YooMoney: invoice created user_id=%s label=%s",
                self.user_id,
                self.ID,
            )
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
        paid = False
        try:
            paid = await self.check_payment()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error('YooMoney: check_payment error', exc_info=e)
        finally:
            if paid:
                await self.delete_pay_button('YooMoney')
            else:
                lang_user = await get_lang(self.session, self.user_id)
                await self.message.answer(_('error_send_admin', lang_user))
                try:
                    await self.message.bot.send_message(
                        CONFIG.admin_tg_id,
                        (
                            "⚠️ YooMoney payment requires manual check\n"
                            f"User ID: {self.user_id}\n"
                            f"Amount: {self.price}\n"
                            f"Label: {self.ID}\n"
                            f"Link: {link_invoice}"
                        ),
                    )
                except Exception:
                    log.exception("failed to notify admin about YooMoney manual check")
                log.info(
                    "YooMoney: payment button kept user_id=%s label=%s",
                    self.user_id,
                    self.ID,
                )
            log.info('exit check payment YooMoney')

    def __str__(self):
        return 'Платежная система YooMoney'
