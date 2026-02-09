import logging
from time import perf_counter

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
    start = perf_counter()
    logger.info('nats consumer start', extra={'event': 'nats_consumer_start', 'subject': subject, 'stream': stream, 'durable': durable_name})
    try:
        await consumer.start()
    except Exception as e:
        logger.error('nats consumer error', extra={'event': 'nats_consumer_error', 'subject': subject, 'stream': stream, 'durable': durable_name}, exc_info=e)
        raise
    finally:
        duration = perf_counter() - start
        logger.info('nats consumer done', extra={'event': 'nats_consumer_done', 'subject': subject, 'stream': stream, 'durable': durable_name, 'duration_s': round(duration, 3)})