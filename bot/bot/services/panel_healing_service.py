import logging

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Servers
from bot.misc.VPN.ServerManager import ServerManager
from bot.services.panel_healing_types import PanelHealResult

log = logging.getLogger(__name__)


async def _load_server(session: AsyncSession, key: Keys) -> Servers | None:
    server = getattr(key, 'server_table', None)
    if server is not None:
        return server
    server_id = getattr(key, 'server', None)
    if server_id is None:
        return None
    return await session.get(Servers, server_id)


async def restore_panel_client_access(
    session: AsyncSession,
    key: Keys | None,
    *,
    reason: str,
    limit_gb: int | None = None,
) -> PanelHealResult:
    if key is None:
        result = PanelHealResult('skipped', None, None, None, None, 'key_missing')
        log.warning(
            'event=panel_client_restore status=%s reason=%s details=%s',
            result.status,
            reason,
            result.details,
        )
        return result

    key_id = getattr(key, 'id', None)
    user_id = getattr(key, 'user_tgid', None)
    server_id = getattr(key, 'server', None)
    server = await _load_server(session, key)
    if server is None:
        result = PanelHealResult(
            'skipped',
            key_id,
            user_id,
            server_id,
            None,
            'server_missing',
        )
        log.warning(
            'event=panel_client_restore status=%s reason=%s key_id=%s user_id=%s details=%s',
            result.status,
            reason,
            key_id,
            user_id,
            result.details,
        )
        return result

    server_id = getattr(server, 'id', server_id)
    try:
        manager = ServerManager(server)
        if not hasattr(manager.client, 'restore_client_access'):
            result = PanelHealResult(
                'skipped',
                key_id,
                user_id,
                server_id,
                None,
                'unsupported_panel',
            )
            log.info(
                'event=panel_client_restore status=%s reason=%s key_id=%s user_id=%s server_id=%s details=%s',
                result.status,
                reason,
                key_id,
                user_id,
                server_id,
                result.details,
            )
            return result

        await manager.login()
        result = await manager.restore_client_access(
            user_id,
            key_id,
            limit_gb=limit_gb,
        )
        log.info(
            'event=panel_client_restore status=%s reason=%s key_id=%s user_id=%s server_id=%s email=%s details=%s',
            result.status,
            reason,
            result.key_id,
            result.user_id,
            result.server_id,
            result.email,
            result.details,
        )
        return result
    except Exception as e:
        result = PanelHealResult(
            'failed',
            key_id,
            user_id,
            server_id,
            None,
            str(e),
        )
        log.error(
            'event=panel_client_restore status=%s reason=%s key_id=%s user_id=%s server_id=%s',
            result.status,
            reason,
            key_id,
            user_id,
            server_id,
            exc_info=e,
        )
        return result
