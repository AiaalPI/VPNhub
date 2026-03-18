import json
import logging
from urllib.parse import parse_qs
from http import HTTPStatus
from typing import Any

from aiogram import Bot
from fastapi import APIRouter, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_payment
from bot.misc.Payment.payment_systems import PaymentSystem
from bot.misc.util import CONFIG
from bot.misc.util import secure_compare
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


def _parse_yoomoney_label(label: Any) -> dict[str, int]:
    if not isinstance(label, str):
        return {}
    # vh1_<user_id>_<type_pay>_<key_id>_<month_count>_<id_prot>_<id_loc>_<price>_<nonce>
    parts = label.split("_")
    if len(parts) != 9 or parts[0] != "vh1":
        return {}
    return {
        "user_id": _coerce_int(parts[1]),
        "type_pay": _coerce_int(parts[2]),
        "key_id": _coerce_int(parts[3]),
        "month_count": _coerce_int(parts[4], default=1),
        "id_prot": _coerce_int(parts[5]),
        "id_loc": _coerce_int(parts[6]),
        "price": _coerce_int(parts[7]),
    }


def _payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = _extract_metadata(payload)
    return {
        "operation_id": payload.get("operation_id"),
        "label": payload.get("label"),
        "notification_type": payload.get("notification_type"),
        "metadata_keys": sorted(metadata.keys()) if isinstance(metadata, dict) else [],
    }


async def _handle_yoomoney_webhook(request: Request) -> Response:
    session: AsyncSession = request.state.session
    bot: Bot = request.state.bot
    request_id = getattr(request.state, "request_id", "unknown")
    raw_body = await request.body()
    body_text = raw_body.decode("utf-8", errors="replace")
    webhook_token = CONFIG.yoomoney_webhook_token
    provided_token = request.headers.get("X-Webhook-Token", "")
    if webhook_token and not secure_compare(provided_token, webhook_token):
        log.warning(
            "event=yoomoney.webhook.rejected request_id=%s reason=invalid_webhook_token",
            request_id,
        )
        return Response(status_code=HTTPStatus.FORBIDDEN)
    log.info(
        "event=yoomoney.webhook.received request_id=%s path=%s content_type=%s content_length=%s",
        request_id,
        request.url.path,
        request.headers.get("content-type"),
        len(raw_body),
    )

    payload: dict[str, Any] = {}
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            payload_candidate = await request.json()
            if isinstance(payload_candidate, dict):
                payload = payload_candidate
        except Exception:
            payload = {}
    if not payload:
        try:
            form = await request.form()
            payload = {key: value for key, value in form.items()}
        except Exception:
            payload = {}
    if not payload and body_text:
        query_payload = parse_qs(body_text, keep_blank_values=True)
        payload = {
            key: values[-1] if isinstance(values, list) and values else values
            for key, values in query_payload.items()
        }

    if not isinstance(payload, dict) or not payload:
        log.warning(
            "event=yoomoney.webhook.empty_payload request_id=%s",
            request_id,
        )
        return Response(status_code=HTTPStatus.OK)
    log.info(
        "event=yoomoney.webhook.payload request_id=%s summary=%s",
        request_id,
        _payload_summary(payload),
    )

    unaccepted = str(payload.get("unaccepted", "")).lower()
    if unaccepted in {"true", "1", "yes"}:
        log.info(
            "event=yoomoney.webhook.unaccepted request_id=%s operation_id=%s",
            request_id,
            payload.get("operation_id"),
        )
        return Response(status_code=HTTPStatus.OK)

    metadata = _extract_metadata(payload)
    label_context = _parse_yoomoney_label(
        metadata.get("label") or payload.get("label")
    )

    user_id = _coerce_int(
        metadata.get("user_id"), default=label_context.get("user_id", 0)
    )
    key_id = _coerce_int(
        metadata.get("key_id"), default=label_context.get("key_id", 0)
    )
    id_prot = _coerce_int(
        metadata.get("id_prot"), default=label_context.get("id_prot", 0)
    )
    id_loc = _coerce_int(
        metadata.get("id_loc"), default=label_context.get("id_loc", 0)
    )
    price = _coerce_int(
        metadata.get("price"), default=label_context.get("price", 0)
    )
    month_count = _coerce_int(
        metadata.get("month_count"), default=label_context.get("month_count", 1)
    )
    message_id = _coerce_int(metadata.get("message_id"), default=1)
    type_pay_code = _coerce_int(
        metadata.get("type_pay"), default=label_context.get("type_pay", 0)
    )
    donate = str(
        metadata.get("donate")
        or CONFIG.type_payment.get(type_pay_code, CONFIG.type_payment.get(0))
    )
    payment_name = str(metadata.get("payment_name", "YooMoneyWebhook"))
    id_payment = metadata.get("id_payment") or payload.get("operation_id")
    log.info(
        "event=yoomoney.webhook.parsed request_id=%s user_id=%s type_pay=%s key_id=%s month_count=%s id_prot=%s id_loc=%s price=%s id_payment=%s label=%s",
        request_id,
        user_id,
        donate,
        key_id,
        month_count,
        id_prot,
        id_loc,
        price,
        id_payment,
        payload.get("label"),
    )

    if user_id <= 0 or price <= 0:
        log.warning(
            "event=yoomoney.webhook.invalid_metadata_values request_id=%s summary=%s",
            request_id,
            _payload_summary(payload),
        )
        return Response(status_code=HTTPStatus.OK)
    if donate == CONFIG.type_payment.get(1) and key_id <= 0:
        log.warning(
            "event=yoomoney.webhook.invalid_extend_payment request_id=%s key_id=%s",
            request_id,
            key_id,
        )
        return Response(status_code=HTTPStatus.OK)

    if id_payment:
        exists = await get_payment(session, id_payment)
        if exists is not None:
            log.info(
                "event=yoomoney.webhook.duplicate request_id=%s id_payment=%s",
                request_id,
                id_payment,
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
