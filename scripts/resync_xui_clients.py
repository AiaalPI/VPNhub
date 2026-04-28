"""
Resync xui (3x-ui / sanaei) panel clients with active subscriptions in DB.

Use case: panel inbound was rebuilt and lost client list. DB still has active
subscriptions but the panel-side clients are gone, so users cannot connect.

For each non-expired key on the requested servers (default: all type_vpn=1),
the script computes the expected email `{user_tgid}.{key_id}.{POST_FIX}`,
checks the panel, and (with --apply) recreates a missing client. Existing
clients are left alone — nobody's working UUID is rotated.

Run inside vpn_hub_bot container so env / deps / imports work:

    docker exec vpn_hub_bot python /app/resync_xui_clients.py [--apply] [--server ID ...]

Default mode is dry-run.
"""
import argparse
import asyncio
import logging
import os
import sys
import time
from typing import Iterable

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
log = logging.getLogger('resync_xui_clients')

sys.path.insert(0, '/app')

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import engine
from bot.database.models.main import Keys, Servers
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.VPN.Xui.XuiBase import XuiBase


async def fetch_active_keys(session, server_ids: Iterable[int] | None):
    now = int(time.time())
    stmt = (
        select(Keys, Servers)
        .join(Servers, Keys.server == Servers.id)
        .where(Keys.subscription >= now)
        .where(Servers.type_vpn == 1)  # VLESS / xui only
    )
    if server_ids:
        stmt = stmt.where(Servers.id.in_(list(server_ids)))
    result = await session.execute(stmt)
    return result.all()


async def list_panel_emails(manager: ServerManager) -> set[str] | None:
    """Pull the inbound's clients via 3x-ui API to enumerate emails."""
    if not isinstance(manager.client, XuiBase):
        return None
    inbound = await manager.client.get_inbound()
    if inbound is None:
        return None
    try:
        clients = inbound.obj.settings.clients  # pyxui_async object
    except AttributeError:
        return None
    return {c.email for c in clients if getattr(c, 'email', None)}


async def process_server(
    server: Servers,
    keys: list[Keys],
    apply: bool,
) -> tuple[list[tuple[Keys, str]], list[tuple[Keys, str, str | None]], set[str]]:
    """Return (already_present, missing[, vless_url_if_applied], orphans)."""
    manager = ServerManager(server)
    await manager.login()
    emails = await list_panel_emails(manager)
    if emails is None:
        log.error('server_id=%s could not load inbound clients', server.id)
        return [], [], set()

    post_fix = manager.client.POST_FIX
    expected = {f'{k.user_tgid}.{k.id}.{post_fix}': k for k in keys}

    already_present: list[tuple[Keys, str]] = []
    missing: list[tuple[Keys, str, str | None]] = []
    for email, key in expected.items():
        if email in emails:
            already_present.append((key, email))
            continue
        new_url: str | None = None
        if apply:
            try:
                new_url = await manager.get_key(
                    name=key.user_tgid,
                    name_key=f'{server.ip}',
                    key_id=key.id,
                )
            except Exception as e:
                log.error('failed to recreate %s: %s', email, e)
        missing.append((key, email, new_url))

    orphans = emails - set(expected.keys())
    return already_present, missing, orphans


async def amain(server_ids: list[int] | None, apply: bool) -> int:
    eng = engine()
    Session = async_sessionmaker(eng, expire_on_commit=False)

    async with Session() as session:
        rows = await fetch_active_keys(session, server_ids)

    by_server: dict[int, tuple[Servers, list[Keys]]] = {}
    for key, server in rows:
        by_server.setdefault(server.id, (server, []))[1].append(key)

    if not by_server:
        log.warning('no active VLESS keys matched the filter')
        return 0

    print()
    print(f"=== resync_xui_clients (apply={apply}) ===")
    for sid, (server, keys) in sorted(by_server.items()):
        print(f"\n--- server id={sid} ip={server.ip} (active keys: {len(keys)}) ---")
        present, missing, orphans = await process_server(server, keys, apply)
        print(f"already in panel: {len(present)}")
        for k, email in present:
            print(f"  OK  key_id={k.id:>4}  user={k.user_tgid:<12} email={email}")
        print(f"missing in panel: {len(missing)}")
        for k, email, url in missing:
            tag = 'CREATED' if url else ('WOULD-CREATE' if not apply else 'FAIL')
            print(f"  {tag}  key_id={k.id:>4}  user={k.user_tgid:<12} email={email}")
            if url:
                print(f"        -> {url}")
        print(f"orphans (in panel, not active in DB): {len(orphans)}")
        for email in sorted(orphans):
            print(f"  ORPHAN  email={email}")

    await eng.dispose()
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--server', type=int, action='append', default=None,
                   help='Limit to server id (repeatable). Default: all xui servers.')
    p.add_argument('--apply', action='store_true',
                   help='Actually create missing clients. Default is dry-run.')
    args = p.parse_args()
    return asyncio.run(amain(args.server, args.apply))


if __name__ == '__main__':
    raise SystemExit(main())
