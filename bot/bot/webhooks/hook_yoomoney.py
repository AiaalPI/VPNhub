import json
import logging
from http import HTTPStatus
from typing import Any

from aiogram import Bot
from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from bot.misc.Payment.payment_systems import PaymentSystem
from bot.webhooks.util import get_message

log = logging.getLogger(__name__)

yoomoney_router = APIRouter()


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
    return metadata if isinstance(metadata, dict) else {}


async def _handle_yoomoney_webhook(request: Request) -> Response:
    session: AsyncSession = request.state.session
    bot: Bot = request.state.bot
    request_id = getattr(request.state, "request_id", "unknown")
    raw_body = await request.body()
    body_text = raw_body.decode("utf-8", errors="replace")
    log.info(
        "event=yoomoney.webhook.received request_id=%s path=%s content_type=%s headers=%s",
        request_id,
        request.url.path,
        request.headers.get("content-type"),
        dict(request.headers),
    )
    log.info(
        "event=yoomoney.webhook.body request_id=%s body=%s",
        request_id,
        body_text,
    )

    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict) or not payload:
        log.warning(
            "event=yoomoney.webhook.empty_payload request_id=%s",
            request_id,
        )
        return Response(status_code=HTTPStatus.OK)

    metadata = _extract_metadata(payload)
    if not metadata:
        log.warning(
            "event=yoomoney.webhook.no_metadata request_id=%s payload_keys=%s",
            request_id,
            list(payload.keys()),
        )
        return Response(status_code=HTTPStatus.OK)

    required_fields = ("user_id", "key_id", "id_prot", "id_loc", "price")
    if not all(field in metadata for field in required_fields):
        log.warning(
            "event=yoomoney.webhook.metadata_incomplete request_id=%s metadata_keys=%s",
            request_id,
            list(metadata.keys()),
        )
        return Response(status_code=HTTPStatus.OK)

    user_id = _coerce_int(metadata.get("user_id"))
    key_id = _coerce_int(metadata.get("key_id"))
    id_prot = _coerce_int(metadata.get("id_prot"))
    id_loc = _coerce_int(metadata.get("id_loc"))
    price = _coerce_int(metadata.get("price"))
    month_count = _coerce_int(metadata.get("month_count"), default=1)
    message_id = _coerce_int(metadata.get("message_id"), default=1)
    donate = str(metadata.get("donate", "new_key"))
    payment_name = str(metadata.get("payment_name", "YooMoneyWebhook"))
    id_payment = metadata.get("id_payment") or payload.get("operation_id")

    if user_id <= 0 or key_id <= 0 or price <= 0:
        log.warning(
            "event=yoomoney.webhook.invalid_metadata_values request_id=%s metadata=%s",
            request_id,
            metadata,
        )
        return Response(status_code=HTTPStatus.OK)

    try:
        message = await get_message(bot, user_id, message_id)
        payment_system = PaymentSystem(
            session=session,
            message=message,
            user_id=user_id,
            donate=donate,
            price=price,
            month_count=month_count,
            id_prot=id_prot,
            id_loc=id_loc,
            key_id=key_id,
        )
        log.info(
            "event=yoomoney.webhook.before_successful_payment request_id=%s user_id=%s key_id=%s id_payment=%s",
            request_id,
            user_id,
            key_id,
            id_payment,
        )
        await payment_system.successful_payment(
            total_amount=price,
            name_payment=payment_name,
            id_payment=id_payment,
        )
        log.info(
            "event=yoomoney.webhook.success request_id=%s user_id=%s key_id=%s",
            request_id,
            user_id,
            key_id,
        )
    except Exception as e:
        log.error(
            "event=yoomoney.webhook.error request_id=%s error=%s",
            request_id,
            str(e),
            exc_info=True,
        )
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    return Response(status_code=HTTPStatus.OK)


@yoomoney_router.post("/payments/yoomoney/webhook")
async def yoomoney_webhook(request: Request) -> Response:
    return await _handle_yoomoney_webhook(request)


@yoomoney_router.post("/payment/yoomoney")
async def yoomoney_webhook_short(request: Request) -> Response:
    return await _handle_yoomoney_webhook(request)


@yoomoney_router.post("/api/v1/payment/yoomoney")
async def yoomoney_webhook_api_v1(request: Request) -> Response:
    return await _handle_yoomoney_webhook(request)
