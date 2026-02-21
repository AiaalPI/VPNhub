import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery, TelegramObject, Update

log = logging.getLogger(__name__)


_HELP_CALLBACKS = {
    "help_menu_btn",
    "help_btn",
    "back_help_menu",
    "back_instructions",
}


def _trim_payload(value: str | None, limit: int = 120) -> str | None:
    if not value:
        return None
    return value if len(value) <= limit else value[:limit]


def _event_type(update: Update) -> str:
    if update.callback_query is not None:
        return "callback_query"
    if update.pre_checkout_query is not None:
        return "pre_checkout_query"
    if update.message is not None:
        return "message"
    return "unknown"


def _extract_user_chat(update: Update) -> tuple[int | None, int | None]:
    if update.callback_query is not None:
        call = update.callback_query
        user_id = getattr(getattr(call, "from_user", None), "id", None)
        chat_id = getattr(getattr(getattr(call, "message", None), "chat", None), "id", None)
        return user_id, chat_id

    if update.pre_checkout_query is not None:
        pcq = update.pre_checkout_query
        user_id = getattr(getattr(pcq, "from_user", None), "id", None)
        return user_id, None

    if update.message is not None:
        msg = update.message
        user_id = getattr(getattr(msg, "from_user", None), "id", None)
        chat_id = getattr(getattr(msg, "chat", None), "id", None)
        return user_id, chat_id

    return None, None


def _message_event(message: Message) -> tuple[str, str | None] | None:
    text = (message.text or "").strip()
    if text.startswith("/start"):
        return "conv.start", _trim_payload(text)
    return None


def _callback_event(call: CallbackQuery) -> tuple[str, str | None] | None:
    payload = (call.data or "").strip()
    payload_l = payload.lower()

    if payload == "vpn_connect_btn":
        return "conv.connect_click", _trim_payload(payload)
    if payload == "back_general_menu_btn":
        return "conv.back_to_menu", _trim_payload(payload)
    if payload in _HELP_CALLBACKS:
        return "conv.help_open", _trim_payload(payload)
    if payload == "message_admin":
        return "conv.support_message", _trim_payload(payload)
    if "pay" in payload_l:
        return "conv.pay_open", _trim_payload(payload)

    return None


def _pre_checkout_event(pcq: PreCheckoutQuery) -> tuple[str, str | None, int | None, str | None]:
    payload = _trim_payload(getattr(pcq, "invoice_payload", None))
    total_amount = getattr(pcq, "total_amount", None)
    currency = getattr(pcq, "currency", None)
    return "conv.pre_checkout", payload, total_amount, currency


class ConversionEventsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Update):
            conv_event: str | None = None
            payload: str | None = None
            total_amount: int | None = None
            currency: str | None = None

            if event.pre_checkout_query is not None:
                conv_event, payload, total_amount, currency = _pre_checkout_event(event.pre_checkout_query)
            elif event.callback_query is not None:
                callback_result = _callback_event(event.callback_query)
                if callback_result is not None:
                    conv_event, payload = callback_result
            elif event.message is not None:
                message_result = _message_event(event.message)
                if message_result is not None:
                    conv_event, payload = message_result

            if conv_event is not None:
                user_id, chat_id = _extract_user_chat(event)
                update_type = _event_type(event)
                if conv_event == "conv.pre_checkout":
                    log.info(
                        "event=%s update_id=%s update_type=%s user_id=%s chat_id=%s payload=%r total_amount=%s currency=%s",
                        conv_event,
                        event.update_id,
                        update_type,
                        user_id,
                        chat_id,
                        payload,
                        total_amount,
                        currency,
                    )
                else:
                    log.info(
                        "event=%s update_id=%s update_type=%s user_id=%s chat_id=%s payload=%r",
                        conv_event,
                        event.update_id,
                        update_type,
                        user_id,
                        chat_id,
                        payload,
                    )

        return await handler(event, data)
