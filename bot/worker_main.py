"""
Standalone NATS consumer worker for VPN key removal.

Runs independently of the Telegram bot process — connects to
NATS + Postgres and processes the DeleteKeyStream queue.
"""
import asyncio
import logging
import signal

from dotenv import load_dotenv

load_dotenv("bot/.env")

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import engine
from bot.misc.nats_connect import connect_to_nats
from bot.misc.remove_key_servise.consumer import RemoveKeyConsumer
from bot.misc.util import CONFIG

log = logging.getLogger("worker")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    shutdown = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown.set)

    log.info("event=worker.starting nats_servers=%s", CONFIG.nats_servers)

    nc, js = await connect_to_nats(CONFIG.nats_servers)
    session_pool = async_sessionmaker(
        engine(), expire_on_commit=False, autoflush=False
    )

    consumer = RemoveKeyConsumer(
        nc=nc,
        js=js,
        bot=None,  # worker does not need the bot instance
        session_pool=session_pool,
        subject=CONFIG.nats_remove_consumer_subject,
        stream=CONFIG.nats_remove_consumer_stream,
        durable_name=CONFIG.nats_remove_consumer_durable_name,
    )

    await consumer.start()
    log.info("event=worker.started subject=%s", CONFIG.nats_remove_consumer_subject)

    await shutdown.wait()

    log.info("event=worker.shutting_down")
    await consumer.unsubscribe()
    await nc.drain()
    log.info("event=worker.stopped")


if __name__ == "__main__":
    asyncio.run(main())
