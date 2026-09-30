"""First-touch referral attribution shared by the website entry and email login."""
import hashlib
import hmac
import time

from sqlalchemy import select

from bot.database.models.main import Persons

COOKIE = "__Secure-kyn_invite"
TTL = 30 * 86400


def sign(secret: str, referrer_id: int, expires_at: int) -> str:
    payload = f"{referrer_id}.{expires_at}"
    signature = hmac.new(secret.encode(), ("invite:" + payload).encode(), hashlib.sha256).hexdigest()
    return payload + "." + signature


def read(secret: str, token: str) -> int | None:
    if not token or len(token) > 128:
        return None
    try:
        referrer, expiry, signature = token.split(".")
        referrer_id, expires_at = int(referrer), int(expiry)
        if not 0 < referrer_id <= 9223372036854775807 or expires_at <= int(time.time()):
            return None
        if hmac.compare_digest(sign(secret, referrer_id, expires_at), token):
            return referrer_id
    except (ValueError, TypeError):
        pass
    return None


async def valid_referrer(session, referrer_id):
    if referrer_id is None:
        return None
    person = await session.scalar(select(Persons).where(Persons.tgid == referrer_id))
    return person.tgid if person and not person.blocked and not person.banned else None


async def from_request(request, config):
    return await valid_referrer(request.state.session, read(config.secret, request.cookies.get(COOKIE, "")))
