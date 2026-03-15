import logging

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import get_key_id, get_name_location_server
from bot.misc.VPN.ServerManager import ServerManager

log = logging.getLogger(__name__)


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
        server_manager = ServerManager(key.server_table, timeout=10)
        await server_manager.login()
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

