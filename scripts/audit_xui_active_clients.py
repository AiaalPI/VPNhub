"""
Audit active DB keys against 3x-ui panel clients.

Run inside the vpn_hub_bot container:

    docker cp scripts/audit_xui_active_clients.py vpn_hub_bot:/app/audit_xui_active_clients.py
    docker exec vpn_hub_bot python /app/audit_xui_active_clients.py
    docker exec vpn_hub_bot python /app/audit_xui_active_clients.py --apply

Default mode is read-only. With --apply, disabled, exhausted, or missing active
clients are restored via the same healing service used after subscription
extensions.
"""
import argparse
import asyncio
import logging
import sys
import time
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

sys.path.insert(0, '/app')

from bot.database import engine
from bot.database.models.main import Keys, Servers
from bot.misc.VPN.ServerManager import ServerManager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
log = logging.getLogger('audit_xui_active_clients')


def _gb(value: int | None) -> float:
    return round((int(value or 0) / 1073741824), 2)


def _client_email(manager: ServerManager, key: Keys) -> str:
    return f'{key.user_tgid}.{key.id}.{manager.client.POST_FIX}'


async def _active_xui_keys(session, server_ids: list[int] | None):
    now = int(time.time())
    stmt = (
        select(Keys, Servers)
        .join(Servers, Keys.server == Servers.id)
        .where(Keys.subscription >= now)
        .where(Servers.type_vpn == 1)
    )
    if server_ids:
        stmt = stmt.where(Servers.id.in_(server_ids))
    rows = (await session.execute(stmt)).all()
    grouped = defaultdict(list)
    for key, server in rows:
        grouped[server.id].append((key, server))
    return grouped


async def _audit_key(manager: ServerManager, key: Keys):
    email = _client_email(manager, key)
    client = await manager.get_user(key.user_tgid, key.id)
    if client is None:
        return {
            'email': email,
            'exists': False,
            'enabled': False,
            'used_gb': 0,
            'limit_gb': 0,
            'exhausted': False,
            'action': 'restore_missing',
        }

    stat = await manager.client.xui.get_client_stat(
        inbound_id=manager.client.inbound_id,
        email=email,
    )
    up = int(getattr(stat, 'up', 0) or 0)
    down = int(getattr(stat, 'down', 0) or 0)
    total = int(getattr(stat, 'total', 0) or getattr(client, 'totalGB', 0) or 0)
    used = up + down
    client_enabled = bool(getattr(client, 'enable', True))
    stat_enabled = bool(getattr(stat, 'enable', True))
    enabled = client_enabled and stat_enabled
    exhausted = bool(total and used >= total)

    action = 'ok'
    if not enabled:
        action = 'restore_disabled'
    elif exhausted:
        action = 'restore_exhausted'

    return {
        'email': email,
        'exists': True,
        'enabled': enabled,
        'used_gb': _gb(used),
        'limit_gb': _gb(total),
        'exhausted': exhausted,
        'action': action,
    }


async def amain(apply: bool, server_ids: list[int] | None) -> int:
    eng = engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)
    restored = 0
    problems = 0

    async with Session() as session:
        grouped = await _active_xui_keys(session, server_ids)
        if not grouped:
            print('active_xui_keys=0')
            await eng.dispose()
            return 0

        for server_id, rows in sorted(grouped.items()):
            server = rows[0][1]
            manager = ServerManager(server)
            await manager.login()
            print(f'\nserver_id={server_id} active_keys={len(rows)}')

            for key, _server in sorted(rows, key=lambda row: row[0].id):
                audit = await _audit_key(manager, key)
                if audit['action'] != 'ok':
                    problems += 1
                print(
                    'key_id={key_id} user={user} email={email} '
                    'exists={exists} enabled={enabled} used_gb={used_gb} '
                    'limit_gb={limit_gb} exhausted={exhausted} action={action}'
                    .format(
                        key_id=key.id,
                        user=key.user_tgid,
                        **audit,
                    )
                )

                if apply and audit['action'] != 'ok':
                    from bot.services.panel_healing_service import (
                        restore_panel_client_access,
                    )

                    result = await restore_panel_client_access(
                        session,
                        key,
                        reason='audit_xui_active_clients',
                    )
                    restored += int(result.status == 'restored')
                    print(
                        f'  apply_status={result.status} details={result.details}'
                    )

    await eng.dispose()
    print(f'\nsummary problems={problems} restored={restored} apply={apply}')
    return 1 if problems and not apply else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--server', type=int, action='append', default=None)
    args = parser.parse_args()
    return asyncio.run(amain(args.apply, args.server))


if __name__ == '__main__':
    raise SystemExit(main())
