import asyncio
import logging

from nats.js.client import JetStreamContext
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.database import engine
from bot.database.methods.delete import delete_not_keys
from bot.database.methods.get import get_server_id
from bot.database.methods.insert import add_not_remove_key
from bot.database.methods.update import server_space_update
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.remove_key_servise.remove_task import TaskRemove
from bot.misc.util import CONFIG


async def remove_key_server(
    js: JetStreamContext,
    subject: str,
    name_key: str,
    key_id: int,
    server_id: int,
    wg_public_key: str = None,
) -> None:
    wg_public_key = wg_public_key or ''
    session_maker = async_sessionmaker(
        engine(),
        expire_on_commit=False,
        autoflush=False
    )
    async def task_with_own_session():
        async with session_maker() as session:
            return await try_direct_delete(
                session, name_key, key_id, server_id, wg_public_key
            )
    direct_delete_task = asyncio.create_task(task_with_own_session())
    task_rm = TaskRemove(
        name_key=str(name_key),
        server_id=server_id,
        key_id=key_id,
        wg_public_key=wg_public_key,
    )
    def publish_if_needed(task) -> None:
        try:
            if not task.result():
                task_json = task_rm.model_dump_json()
                asyncio.create_task(
                    js.publish(subject=subject, payload=task_json.encode())
                )
                logging.info(
                    f'Published removal task for {name_key}.{key_id} to queue'
                )
        except Exception as e:
            logging.error('Error in callback:', exc_info=e)
            task_json = task_rm.model_dump_json()
            asyncio.create_task(
                js.publish(subject=subject, payload=task_json.encode())
            )
    direct_delete_task.add_done_callback(publish_if_needed)



async def try_direct_delete(
    session: AsyncSession,
    name_key: str,
    key_id: int,
    server_id: int,
    wg_public_key: str = None
) -> bool:
    """Пытается удалить ключ напрямую, возвращает True если успешно"""
    server = await get_server_id(session, server_id)
    if server is None:
        logging.info(
            f'Server {server_id} not found for key {name_key}.{key_id}'
        )
        return True
    try:
        server_manager = ServerManager(server)
        await server_manager.login()
        if server.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
            success = await server_manager.delete_client(
                wg_public_key, key_id
            )
        else:
            success = await server_manager.delete_client(name_key, key_id)
        if success:
            logging.info(
                f'Key {name_key}.{key_id} publisher '
                f'deleted from server {server_id} - OK'
            )
            await delete_not_keys(
                session,
                str(name_key),
                int(key_id),
                int(server_id)
            )
            try:
                all_client = await server_manager.get_all_user()
                await server_space_update(
                    session, server.id, len(all_client)
                )
            except Exception as e:
                logging.error(e)
            return True
    except Exception as e:
        logging.error(
            f'Direct delete failed for '
            f'key {name_key}.{key_id} on server {server_id}:',
            exc_info=e
        )
        await add_not_remove_key(
            session,
            str(name_key),
            int(key_id),
            int(server_id)
        )
    return False
