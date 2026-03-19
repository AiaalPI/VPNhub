"""
Standalone NATS consumer worker for VPN key removal.

Runs independently of the Telegram bot process — connects to
NATS + Postgres and processes the DeleteKeyStream queue.
"""
import asyncio
import contextlib
import logging
from pathlib import Path
import signal
import time

from dotenv import load_dotenv

load_dotenv("bot/.env")

from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import engine
from bot.misc.nats_connect import connect_to_nats
from bot.misc.remove_key_servise.consumer import RemoveKeyConsumer
from bot.misc.util import CONFIG

log = logging.getLogger("worker")
HEARTBEAT_FILE = Path("/tmp/nats_worker_heartbeat")
HEARTBEAT_INTERVAL_SEC = 10


async def heartbeat_loop(shutdown: asyncio.Event) -> None:
    while not shutdown.is_set():
        HEARTBEAT_FILE.write_text(str(int(time.time())), encoding="utf-8")
        try:
            await asyncio.wait_for(
                shutdown.wait(),
                timeout=HEARTBEAT_INTERVAL_SEC,
            )
        except TimeoutError:
            continue


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    shutdown = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown.set)
        except NotImplementedError:
            pass

    log.info("event=worker.starting nats_servers=%s", CONFIG.nats_servers)

    nc, js = await connect_to_nats(CONFIG.nats_servers)
    engine_instance = engine()
    session_pool = async_sessionmaker(
        engine_instance, expire_on_commit=False, autoflush=False
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

    heartbeat_task = asyncio.create_task(
        heartbeat_loop(shutdown),
        name="worker-heartbeat",
    )
    try:
        await consumer.start()
        log.info(
            "event=worker.started subject=%s",
            CONFIG.nats_remove_consumer_subject
        )

        await shutdown.wait()
    finally:
        log.info("event=worker.shutting_down")
        heartbeat_task.cancel()
        with contextlib.suppress(Exception):
            await heartbeat_task
        with contextlib.suppress(FileNotFoundError):
            HEARTBEAT_FILE.unlink()
        await consumer.stop()
        await nc.drain()
        await engine_instance.dispose()
        log.info("event=worker.stopped")


if __name__ == "__main__":
    asyncio.run(main())
