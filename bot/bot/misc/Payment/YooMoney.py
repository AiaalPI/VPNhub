import asyncio
import json
import logging
import random
import uuid
from collections.abc import Iterable

from aiohttp import client_exceptions
from yoomoney_async import Quickpay, Client

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

    @staticmethod
    def _to_dict_if_json(value):
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return None
        return None

    @classmethod
    def _extract_operations(cls, response):
        operations = getattr(response, "operations", None)
        if isinstance(operations, (list, tuple)):
            return list(operations)
        if isinstance(operations, Iterable) and not isinstance(
            operations, (str, bytes, dict)
        ):
            return list(operations)

        parsed = cls._to_dict_if_json(response)
        if parsed is not None:
            operations = parsed.get("operations")
            if isinstance(operations, (list, tuple)):
                return list(operations)
            return []

        if isinstance(response, dict):
            operations = response.get("operations")
            if isinstance(operations, (list, tuple)):
                return list(operations)
            return []
        return []

    @classmethod
    def _extract_amount(cls, operation):
        amount = getattr(operation, "amount", None)
        if amount is not None:
            return amount
        parsed = cls._to_dict_if_json(operation)
        if parsed is not None:
            return parsed.get("amount")
        if isinstance(operation, dict):
            return operation.get("amount")
        if hasattr(operation, "__dict__"):
            amount = operation.__dict__.get("amount")
            if amount is not None:
                return amount
        return getattr(operation, "amount", None)

    async def check_payment(self):
        client = Client(self.TOKEN)
        tic = 0
        while tic < self.CHECK_PERIOD:
            response = None
            try:
                response = await client.operation_history(label=self.ID)
                log.info(f"RESPONSE TYPE: {type(response)}")
                log.info(
                    f"RESPONSE DIR: {[x for x in dir(response) if not x.startswith('_')]}"
                )
                if hasattr(response, "operations"):
                    ops = response.operations
                    log.info(f"OPS TYPE: {type(ops)}")
                    try:
                        ops_list = list(ops)
                    except TypeError:
                        ops_list = []
                    if ops_list:
                        log.info(f"FIRST OP TYPE: {type(ops_list[0])}")
                        log.info(
                            f"FIRST OP DIR: {[x for x in dir(ops_list[0]) if not x.startswith('_')]}"
                        )
                operations = self._extract_operations(response)
                if not operations:
                    log.warning("YooMoney: operations not found in response type=%s", type(response).__name__)
                for operation in operations:
                    amount = self._extract_amount(operation)
                    if amount is None:
                        log.warning("YooMoney: operation without amount: %s", operation)
                        continue
                    cal_amount = self.price - self.price * 0.04
                    if float(amount) < cal_amount:
                        continue
                    await self.successful_payment(self.price, 'YooMoney')
                    return
            except client_exceptions.ClientOSError:
                log.info('YooMoney: ClientOSError — retrying')
            except (TypeError, KeyError, ValueError) as e:
                log.error(
                    f"RAW TYPE: {type(response)} RAW VALUE: {repr(response)[:500]}"
                )
                log.error("YooMoney raw response: %s", response)
                log.warning('YooMoney: bad API response, retrying: %s', e)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.error(
                    f"RAW TYPE: {type(response)} RAW VALUE: {repr(response)[:500]}"
                )
                log.error("YooMoney raw response: %s", response)
                log.warning('YooMoney: unexpected error in poll loop, retrying: %s', e)
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
