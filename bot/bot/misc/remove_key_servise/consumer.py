import asyncio
import json
import logging

from aiogram import Bot

from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.js import JetStreamContext, api
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database.methods.delete import delete_not_keys
from bot.database.methods.get import get_server_id
from bot.database.methods.update import server_space_update
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.remove_key_servise.remove_task import TaskRemove
from bot.misc.util import CONFIG

logger = logging.getLogger(__name__)

class RemoveKeyConsumer:
    def __init__(
        self,
        nc: Client,
        js: JetStreamContext,
        bot: Bot,
        session_pool: async_sessionmaker,
        subject: str,
        stream: str,
        durable_name: str
    ) -> None:
        self.nc = nc
        self.js = js
        self.bot = bot
        self.subject = subject
        self.stream = stream
        self.durable_name = durable_name
        self.session_pool = session_pool

    async def start(self) -> None:
        consumer_config = api.ConsumerConfig(
            ack_wait=5 * 60,
            max_deliver=10,
        )
        self.stream_sub = await self.js.pull_subscribe(
            subject=self.subject,
            stream=self.stream,
            durable=self.durable_name,
            config=consumer_config,
        )
        asyncio.create_task(self.worker())

    async def worker(self):
        while True:
            try:
                msgs = await self.stream_sub.fetch(1, timeout=5)
            except TimeoutError:
                continue

            for msg in msgs:
                try:
                    await self.on_message(msg)
                except Exception as e:
                    logger.exception("Unhandled error in consumer")

    async def on_message(self, msg: Msg):
        data = json.loads(msg.data.decode())
        if data.get("wg_public_key") is None:
            data['wg_public_key'] = ''
        task = TaskRemove(**data)
        async with self.session_pool() as session:
            server = await get_server_id(session, task.server_id)
            if server is None:
                logger.info(
                    f'The server where the key {task.name_key}.{task.key_id}'
                    f'should have been deleted was not found'
                )
                await msg.ack()
                return
        try:
            server_manager = ServerManager(server)
            await server_manager.login()
            if server.type_vpn == CONFIG.TypeVpn.WIREGUARD.value:
                success = await server_manager.delete_client(
                    task.wg_public_key, task.key_id
                )
            else:
                success = await server_manager.delete_client(
                    task.name_key, task.key_id
                )
            if success:
                logger.info(
                    f'The key {task.name_key}.{task.key_id} '
                    f'deleted from the server id {server.id}'
                )
                async with self.session_pool() as session:
                    await delete_not_keys(
                        session,
                        str(task.name_key),
                        int(task.key_id),
                        int(task.server_id)
                    )
                try:
                    server_parameters = await server_manager.get_all_user()
                    async with self.session_pool() as session:
                        await server_space_update(
                            session,
                            server.id,
                            len(server_parameters)
                        )
                    logger.info(f'Server id {server.id} space updated')
                except Exception as e:
                    logger.error(
                        f'Error update server id {server.id} space',
                        exc_info=e
                    )
                finally:
                    await msg.ack()
            else:
                raise ConnectionError()
        except Exception as e:
            logger.error(
                f"Not delete the key {task.name_key}.{task.key_id} "
                f"from the server id {server.id} "
                f"Next attempt in {CONFIG.delay_remove_key} seconds"
            )
            logger.error(e)
            await msg.nak(delay=CONFIG.delay_remove_key)

    async def unsubscribe(self) -> None:
        if self.stream_sub:
            await self.stream_sub.unsubscribe()
            logger.info('Consumer unsubscribed')