import asyncio
import aiohttp
import json
import logging
import random
import uuid
from urllib.parse import urlencode, quote
from aiohttp import client_exceptions
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.keyboards.inline.user_inline import payment_support_keyboard
from bot.misc.language import Localization, get_lang
from bot.misc.callbackData import YooMoneyManualModeration
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

_ = Localization.text


class YooMoney(PaymentSystem):
    CHECK_ID: str = None
    ID: str = None
    CHECK_PERIOD = 60

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
        type_pay_code = 0
        for code, value in CONFIG.type_payment.items():
            if value == self.TYPE_PAYMENT:
                type_pay_code = int(code)
                break

        key_id = int(self.KEY_ID or 0)
        month_count = int(self.month_count or 1)
        id_prot = int(self.ID_PROT or 0)
        id_loc = int(self.ID_LOC or 0)
        price = int(self.price or 0)
        nonce = uuid.uuid4().hex[:8]
        label = (
            f"vh1_{self.user_id}_{type_pay_code}_{key_id}_{month_count}_"
            f"{id_prot}_{id_loc}_{price}_{nonce}"
        )
        self.ID = label if len(label) <= 64 else str(uuid.uuid4())

    async def check_payment(self):
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            "Authorization": f"Bearer {self.TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        tic = 0
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=timeout,
        ) as http:
            while tic < self.CHECK_PERIOD:
                try:
                    log.info(
                        "YooMoney polling URL: https://yoomoney.ru/api/operation-history label=%s",
                        self.ID,
                    )
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
                        if resp.status >= 500:
                            log.warning(
                                "YooMoney poll temporary server error status=%s body=%s",
                                resp.status,
                                raw_text[:500],
                            )
                            tic += self.STEP
                            await asyncio.sleep(self.STEP)
                            continue
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
                except (client_exceptions.ConnectionTimeoutError, TimeoutError) as e:
                    # Network hiccup: keep polling until CHECK_PERIOD window ends.
                    log.warning("YooMoney check timeout: %s", e, exc_info=True)
                except client_exceptions.ClientError as e:
                    # Temporary client/network errors should not fail payment immediately.
                    log.warning("YooMoney check client error: %s", e, exc_info=True)
                except Exception as e:
                    # Keep retrying to avoid false negative payment status due to transient issues.
                    log.error(f"YooMoney check error: {e}", exc_info=True)
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
            await self._notify_payment_not_completed()
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
                await self._notify_payment_not_completed()
                try:
                    admin_lang = await get_lang(self.session, CONFIG.admin_tg_id)
                    type_pay_code = 0
                    for code, value in CONFIG.type_payment.items():
                        if value == self.TYPE_PAYMENT:
                            type_pay_code = code
                            break
                    kb = InlineKeyboardBuilder()
                    kb.button(
                        text=_('review_admin_approve_btn', admin_lang),
                        callback_data=YooMoneyManualModeration(
                            action='approve',
                            user_id=self.user_id,
                            price=int(self.price),
                            month_count=int(self.month_count or 1),
                            key_id=int(self.KEY_ID or 0),
                            id_prot=int(self.ID_PROT or 0),
                            id_loc=int(self.ID_LOC or 0),
                            type_pay=int(type_pay_code),
                        ),
                    )
                    kb.button(
                        text=_('review_admin_reject_btn', admin_lang),
                        callback_data=YooMoneyManualModeration(
                            action='reject',
                            user_id=self.user_id,
                            price=int(self.price),
                            month_count=int(self.month_count or 1),
                            key_id=int(self.KEY_ID or 0),
                            id_prot=int(self.ID_PROT or 0),
                            id_loc=int(self.ID_LOC or 0),
                            type_pay=int(type_pay_code),
                        ),
                    )
                    kb.adjust(2)
                    await self.message.bot.send_message(
                        CONFIG.admin_tg_id,
                        (
                            "⚠️ YooMoney payment requires manual check\n"
                            f"User ID: {self.user_id}\n"
                            f"Amount: {self.price}\n"
                            f"Label: {self.ID}\n"
                            f"Link: {link_invoice}"
                        ),
                        reply_markup=kb.as_markup(),
                    )
                    log.info(
                        "YooMoney: manual check requested admin_id=%s user_id=%s label=%s",
                        CONFIG.admin_tg_id,
                        self.user_id,
                        self.ID,
                    )
                except Exception:
                    log.exception("failed to notify admin about YooMoney manual check")
                log.info(
                    "YooMoney: payment button kept user_id=%s label=%s",
                    self.user_id,
                    self.ID,
                )
        log.info('exit check payment YooMoney')

    async def _notify_payment_not_completed(self):
        lang_user = await get_lang(self.session, self.user_id)
        await self.message.answer(
            _('payment_failed_retry_support', lang_user),
            reply_markup=await payment_support_keyboard(lang_user),
        )

    def __str__(self):
        return 'Платежная система YooMoney'
