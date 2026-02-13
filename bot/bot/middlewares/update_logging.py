import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

log = logging.getLogger(__name__)


def _extract_event(update: Update) -> tuple[str, TelegramObject | None]:
    event_type = getattr(update, "event_type", None)
    if event_type and hasattr(update, event_type):
        return event_type, getattr(update, event_type)

    for candidate in ("message", "edited_message", "callback_query", "inline_query"):
        event = getattr(update, candidate, None)
        if event is not None:
            return candidate, event
    return "unknown", None


def _event_payload(event: TelegramObject | None) -> str | None:
    if isinstance(event, Message):
        return event.text or event.caption
    if isinstance(event, CallbackQuery):
        return event.data
    return None


def _event_user_chat(event: TelegramObject | None) -> tuple[int | None, int | None]:
    user_id = getattr(getattr(event, "from_user", None), "id", None)
    chat_id = getattr(getattr(event, "chat", None), "id", None)
    if chat_id is None and isinstance(event, CallbackQuery):
        chat_id = getattr(getattr(event.message, "chat", None), "id", None)
    return user_id, chat_id


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        event_type, inner_event = _extract_event(event)
        user_id, chat_id = _event_user_chat(inner_event)
        payload = _event_payload(inner_event)
        log.info(
            "update.in id=%s type=%s user_id=%s chat_id=%s payload=%r",
            event.update_id,
            event_type,
            user_id,
            chat_id,
            payload,
        )
        try:
            result = await handler(event, data)
            log.info(
                "update.out id=%s type=%s handled=%s",
                event.update_id,
                event_type,
                bool(result),
            )
            return result
        except Exception:
            log.exception(
                "update.error id=%s type=%s user_id=%s chat_id=%s",
                event.update_id,
                event_type,
                user_id,
                chat_id,
            )
            raise


class RouteLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        handler_obj = data.get("handler")
        callback = getattr(handler_obj, "callback", None)
        if callback is not None:
            handler_name = f"{callback.__module__}.{callback.__name__}"
        else:
            handler_name = repr(handler_obj)

        user_id, chat_id = _event_user_chat(event)
        payload = _event_payload(event)
        log.info(
            "route.enter event=%s handler=%s user_id=%s chat_id=%s payload=%r",
            type(event).__name__,
            handler_name,
            user_id,
            chat_id,
            payload,
        )
        try:
            result = await handler(event, data)
            log.info(
                "route.exit event=%s handler=%s status=ok",
                type(event).__name__,
                handler_name,
            )
            return result
        except Exception:
            log.exception(
                "route.error event=%s handler=%s user_id=%s chat_id=%s",
                type(event).__name__,
                handler_name,
                user_id,
                chat_id,
            )
            raise
