"""Small, explicit authentication and payment-validation primitives."""

import hashlib
import hmac
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def code_digest(secret: str, challenge: str, code: str) -> str:
    return hmac.new(secret.encode(), f"login:{challenge}:{code}".encode(), hashlib.sha256).hexdigest()


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    # Deliberately accept a conservative, interoperable SMTP address subset.
    if len(value) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}", value):
        raise ValueError("Некорректный email")
    return value


def verify_notification(payload: dict[str, str], secret: str) -> bool:
    """YooMoney's current HMAC-SHA256 scheme, including ALL signed fields."""
    if not secret or not re.fullmatch(r"[0-9a-f]{64}", payload.get("sign", "")):
        return False
    canonical = urlencode(sorted((k, v) for k, v in payload.items() if k != "sign"))
    expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, payload["sign"])


def paid_amount(payload: dict[str, str]) -> int:
    """Use signed gross amount; wallet credit may exclude the provider fee."""
    if (payload.get("currency") != "643"
            or payload.get("notification_type") not in {"p2p-incoming", "card-incoming"}
            or payload.get("unaccepted", "false") != "false"
            or payload.get("codepro", "false") != "false"):
        raise ValueError("Payment is not settled in RUB")
    try:
        amount = Decimal(payload["withdraw_amount"])
        if not amount.is_finite() or amount <= 0 or amount * 100 != (amount * 100).to_integral_value():
            raise ValueError("Invalid payment amount")
        return int(amount * 100)
    except (KeyError, InvalidOperation) as exc:
        raise ValueError("Invalid payment amount") from exc
