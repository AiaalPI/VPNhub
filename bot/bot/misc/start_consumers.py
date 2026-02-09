import logging

from aiogram import Bot
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.misc.remove_key_servise.consumer import RemoveKeyConsumer

from nats.aio.client import Client
from nats.js.client import JetStreamContext

logger = logging.getLogger(__name__)


async def start_delayed_consumer(
    nc: Client,
    js: JetStreamContext,
    bot: Bot,
    session_pool: async_sessionmaker,
    subject: str,
    stream: str,
    durable_name: str
) -> None:
    consumer = RemoveKeyConsumer(
        nc=nc,
        js=js,
        bot=bot,
        session_pool=session_pool,
        subject=subject,
        stream=stream,
        durable_name=durable_name
    )
    logger.info('Start remove key consumer')
    await consumer.start()