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
    logger.info('job.nats_consumer.start', extra={'subject': subject, 'stream': stream, 'durable': durable_name})
    try:
        await consumer.start()
    except Exception as e:
        logger.error('job.nats_consumer.error', exc_info=e)
        raise
    finally:
        duration = perf_counter() - start
        logger.info('job.nats_consumer.done', extra={'subject': subject, 'stream': stream, 'durable': durable_name, 'duration_s': round(duration,3)})