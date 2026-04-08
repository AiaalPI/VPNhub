import logging
import base64
import hashlib
import hmac
import time

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from httpx import HTTPStatusError

from bot.database.methods.get import get_key_id, get_name_location_server
from bot.misc.VPN.Marzban import Marzban
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

_TOKEN_TTL_SEC = 60 * 60 * 24 * 30


def _token_signature(payload: str) -> str:
    return hmac.new(
        CONFIG.subscription_signing_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _urlsafe_b64encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8")).decode("utf-8")


def build_clean_subscription_token(user_id: int, key_id: int, issued_at: int | None = None) -> str:
    issued_at = int(issued_at or time.time())
    payload = f"{int(user_id)}:{int(key_id)}:{issued_at}"
    signature = _token_signature(payload)
    return _urlsafe_b64encode(f"{payload}:{signature}")


def parse_clean_subscription_token(token: str) -> tuple[int, int]:
    try:
        decoded = _urlsafe_b64decode(token)
        user_id_raw, key_id_raw, issued_at_raw, signature = decoded.split(":", 3)
        payload = f"{user_id_raw}:{key_id_raw}:{issued_at_raw}"
        if not hmac.compare_digest(signature, _token_signature(payload)):
            raise ValueError("bad_signature")
        issued_at = int(issued_at_raw)
        if issued_at + _TOKEN_TTL_SEC < int(time.time()):
            raise ValueError("expired")
        return int(user_id_raw), int(key_id_raw)
    except Exception as exc:
        raise HTTPException(status_code=403, detail="invalid_subscription_token") from exc


def build_clean_subscription_url(user_id: int, key_id: int) -> str | None:
    if not CONFIG.public_subscription_base:
        return None
    token = build_clean_subscription_token(user_id=user_id, key_id=key_id)
    return f"{CONFIG.public_subscription_base}/subscriptions/{token}"


async def get_clean_marzban_links(
    session: AsyncSession,
    key_id: int,
    user_id: int,
) -> list[str]:
    key = await get_key_id(session, key_id)
    if (
        key is None
        or key.server is None
        or int(getattr(key, "user_tgid", 0) or 0) != int(user_id)
    ):
        return []
    server_manager = ServerManager(key.server_table, timeout=10)
    await server_manager.login()
    if not isinstance(server_manager.client, Marzban):
        subscription_link = await server_manager.get_key(
            name=user_id,
            name_key=await get_name_location_server(session, key.server_table.id),
            key_id=key.id,
            subscription_timestamp=key.subscription,
        )
        return [subscription_link] if isinstance(subscription_link, str) and subscription_link.strip() else []

    marzban_username = f"{user_id}.{key.id}.{server_manager.client.POST_FIX}"
    try:
        user = await server_manager.client.get_client(marzban_username)
    except HTTPStatusError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        # Recovery path: recreate missing Marzban user for an existing key
        # and retry loading links for clean subscription payload.
        location_name = await get_name_location_server(session, key.server_table.id)
        await server_manager.get_key(
            name=user_id,
            name_key=location_name,
            key_id=key.id,
            subscription_timestamp=key.subscription,
        )
        user = await server_manager.client.get_client(marzban_username)
    links = user.get("links") or []
    clean_links = []
    for raw_link in links:
        if not isinstance(raw_link, str) or not raw_link.strip():
            continue
        normalized = server_manager.client.normalize_export_link(raw_link)
        if server_manager.client._is_degraded_export_link(normalized):
            continue
        clean_links.append(normalized)
    return clean_links


async def render_clean_subscription_payload(
    session: AsyncSession,
    key_id: int,
    user_id: int,
) -> str:
    links = await get_clean_marzban_links(session=session, key_id=key_id, user_id=user_id)
    if not links:
        raise HTTPException(status_code=404, detail="subscription_not_found")
    return "\n".join(links)


async def get_user_subscription_link(
    session: AsyncSession,
    key_id: int,
    user_id: int,
) -> str | None:
    """
    Return unified Marzban subscription link for user key.

    Link is generated/retrieved via existing ServerManager integration and
    remains the single source for Finland/Japan server list inside client.
    """
    key = await get_key_id(session, key_id)
    if key is None or key.server is None:
        return None
    try:
        clean_subscription_url = build_clean_subscription_url(user_id=user_id, key_id=key_id)
        if clean_subscription_url:
            return clean_subscription_url
        server_manager = ServerManager(key.server_table, timeout=10)
        await server_manager.login()
        if isinstance(server_manager.client, Marzban):
            primary_link = await server_manager.client.get_primary_link(
                f"{user_id}.{key.id}.{server_manager.client.POST_FIX}"
            )
            if isinstance(primary_link, str) and primary_link.strip():
                return primary_link
        location_name = await get_name_location_server(session, key.server_table.id)
        subscription_link = await server_manager.get_key(
            name=user_id,
            name_key=location_name,
            key_id=key.id,
            subscription_timestamp=key.subscription,
        )
        if isinstance(subscription_link, str) and subscription_link.strip():
            return subscription_link
        return None
    except Exception:
        log.exception(
            "event=subscription_link status=failed user_id=%s key_id=%s",
            user_id,
            key_id,
        )
        return None
