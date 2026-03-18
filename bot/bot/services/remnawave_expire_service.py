import inspect
import logging
from datetime import datetime, timedelta, timezone

from bot.database.methods.get import get_key_id
from bot.database.models.main import Keys
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)


def sinc_time(func):
    """Sync expiration time with the provider after DB writes complete."""

    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        args_dict = bound_args.arguments
        session = args_dict.get('session')
        key_id = args_dict.get('key_id')
        if session is not None and key_id is not None:
            key = await get_key_id(session, int(key_id))
            await sync_remnawave_expire(key)
        return result

    return wrapper


async def sync_remnawave_expire(key: Keys):
    """Synchronize subscription expiration with the Remnawave panel."""
    try:
        from bot.misc.VPN.ServerManager import ServerManager

        server_manager = ServerManager(key.server_table)
        await server_manager.login()

        utc_plus = timezone(timedelta(hours=CONFIG.UTC_time))
        expire_at = datetime.fromtimestamp(key.subscription, tz=utc_plus)

        await server_manager.update_user_expire(
            key.user_tgid,
            key.id,
            expire_at,
        )
        log.info(
            "Synced Remnawave expire for key %s, user %s, expire: %s",
            key.id,
            key.user_tgid,
            expire_at,
        )
    except Exception as e:
        log.error("Failed to sync Remnawave expire for key %s: %s", key.id, e)
