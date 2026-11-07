"""Read panel accounting without resetting traffic or changing allowances."""

import asyncio
import logging
from dataclasses import dataclass

from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.VPN.Xui.Vless import Vless

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionUsage:
    upload: int
    download: int
    total: int


def _bytes(value) -> int:
    # Missing or malformed counters must not turn a finite plan into unlimited.
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("Invalid panel accounting value")
    return value


def usage_from_global_clients(response: dict, email: str) -> SubscriptionUsage:
    if not isinstance(response, dict) or response.get("success") is not True:
        raise ValueError("Panel accounting unavailable")
    matches = [row for row in response.get("obj") or [] if row.get("email") == email]
    if len(matches) != 1:
        raise ValueError("Panel client accounting not unique")
    row = matches[0]
    traffic = row.get("traffic")
    if not isinstance(traffic, dict):
        raise ValueError("Panel traffic counters unavailable")
    # The global client has one aggregate across REALITY and XHTTP. Do not
    # multiply it by its inbound attachments or round bytes to displayed GiB.
    return SubscriptionUsage(
        upload=_bytes(traffic.get("up")),
        download=_bytes(traffic.get("down")),
        total=_bytes(row.get("totalGB")),
    )


async def get_subscription_usage(key, user_id: int, session=None) -> SubscriptionUsage | None:
    if key is None or int(key.user_tgid) != int(user_id) or key.server is None:
        return None
    if session is not None:
        from bot.services.shared_subscriptions import group_for_key, usage
        group = await group_for_key(session, key.id)
        if group:
            try:
                return await usage(session, group.account_id)
            except Exception as exc:
                log.warning('event=shared_subscription_accounting_unavailable reason=%s', type(exc).__name__)
                return None
    manager = ServerManager(key.server_table, timeout=4)
    if not isinstance(getattr(manager, "client", None), Vless):
        return None
    xui = manager.client.xui
    try:
        async with asyncio.timeout(6):
            await manager.login()
            response = await xui.request(method="GET", endpoint="/panel/api/clients/list")
            usage = usage_from_global_clients(response, f"{user_id}.{key.id}.vl")
            if session is not None:
                from sqlalchemy import select
                from bot.database.models.main import TrafficPolicy
                from bot.services.monthly_traffic_service import monthly_usage
                policy = await session.scalar(select(TrafficPolicy).where(TrafficPolicy.key_id == key.id))
                usage = monthly_usage(usage, policy)
            return usage
    except Exception as exc:
        # Do not log panel URLs, credentials, client identities, or signed URLs.
        log.warning("event=subscription_accounting_unavailable reason=%s", type(exc).__name__)
        return None
    finally:
        try:
            await xui.close()
        except Exception as exc:
            log.warning("event=subscription_accounting_close_failed reason=%s", type(exc).__name__)
