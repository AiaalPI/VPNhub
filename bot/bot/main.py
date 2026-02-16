import asyncio
import logging
import signal
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramConflictError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import engine
from bot.filters.is_private import PrivateFilter
from bot.handlers.other.main import other_router
from bot.handlers.user.edit_or_get_key import get_key_router
from bot.handlers.user.main import user_router, registered_router
from bot.handlers.admin.main import admin_router
from bot.database.importBD.import_BD import import_all
from bot.middlewares.session import DbSessionMiddleware
from bot.middlewares.update_logging import (
    RouteLoggingMiddleware,
    UpdateLoggingMiddleware,
)
from bot.misc.commands import set_commands
from bot.misc.loop import loop as scheduler_loop_job
from bot.misc.nats_connect import connect_to_nats
from bot.misc.start_consumers import start_delayed_consumer
from bot.misc.util import CONFIG
from bot.service.send_dump import send_dump
from bot.service.server_controll_manager import server_control_manager
from bot.webhooks import app as fastapi_app

log = logging.getLogger(__name__)


async def run_polling_with_retries(
    dp: Dispatcher,
    bot: Bot,
    js,
    remove_key_subject: str,
    allowed_updates: list[str],
    shutdown_event: asyncio.Event,
) -> None:
    attempt = 1
    delay = 1.0
    max_delay = 60.0
    while not shutdown_event.is_set():
        try:
            log.info(
                "event=polling.start attempt=%d allowed_updates=%s",
                attempt,
                allowed_updates,
            )
            await dp.start_polling(
                bot,
                js=js,
                remove_key_subject=remove_key_subject,
                allowed_updates=allowed_updates,
            )
            if shutdown_event.is_set():
                log.info("event=polling.stop reason=shutdown")
                return
            log.warning(
                "event=polling.stop reason=unexpected_return action=retry backoff_sec=%.1f",
                delay,
            )
        except TelegramConflictError:
            log.error(
                "event=polling.conflict attempt=%d action=retry backoff_sec=%.1f",
                attempt,
                delay,
            )
        except Exception:
            log.exception(
                "event=polling.error attempt=%d action=retry backoff_sec=%.1f",
                attempt,
                delay,
            )
        await asyncio.sleep(delay)
        attempt += 1
        delay = min(delay * 2, max_delay)


async def start_bot():
    shutdown_event = asyncio.Event()
    bot = Bot(
        token=CONFIG.tg_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    log.info("event=startup.nats_connect")
    nc, js = await connect_to_nats(servers=CONFIG.nats_servers)
    log.info("event=startup.nats_connected servers=%s", CONFIG.nats_servers)

    dp = Dispatcher(
        storage=MemoryStorage(),
        fsm_strategy=FSMStrategy.USER_IN_CHAT
    )
    dp.include_routers(
        registered_router,
        user_router,
        get_key_router,
        admin_router,
        other_router
    )
    dp.message.filter(PrivateFilter())

    if CONFIG.import_bd:
        await import_all()
        log.info('event=startup.import_db status=ok')
        await nc.close()
        await bot.session.close()
        return
    engine_instance = engine()
    sessionmaker = async_sessionmaker(
        engine_instance,
        expire_on_commit=False
    )
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    dp.update.outer_middleware(UpdateLoggingMiddleware())
    dp.message.middleware(RouteLoggingMiddleware())
    dp.callback_query.middleware(RouteLoggingMiddleware())
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    await set_commands(bot)
    scheduler.add_job(
        scheduler_loop_job,
        "interval",
        seconds=60,
        args=(bot,sessionmaker, js, CONFIG.nats_remove_consumer_subject)
    )
    scheduler.add_job(
        send_dump,
        CronTrigger(hour=0, minute=0),
        args=(bot,),
        replace_existing=True,
    )
    scheduler.add_job(
        server_control_manager,
        "interval",
        seconds=900,
        args=(bot, sessionmaker),
        replace_existing=True
    )
    logging.getLogger('apscheduler.executors.default').setLevel(
        logging.WARNING
    )
    scheduler.start()
    log.info("event=scheduler.started")

    event_loop = asyncio.get_running_loop()

    def _signal_handler(signum: int) -> None:
        log.warning("event=shutdown.signal signum=%s", signum)
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            event_loop.add_signal_handler(sig, _signal_handler, sig)
        except NotImplementedError:
            pass

    tasks: list[asyncio.Task] = []
    wait_shutdown_task: asyncio.Task | None = None
    try:
        allowed_updates = dp.resolve_used_update_types()
        log.info("event=startup.polling_ready allowed_updates=%s", allowed_updates)
        await start_delayed_consumer(
            nc=nc,
            js=js,
            bot=bot,
            session_pool=sessionmaker,
            subject=CONFIG.nats_remove_consumer_subject,
            stream=CONFIG.nats_remove_consumer_stream,
            durable_name=CONFIG.nats_remove_consumer_durable_name
        )
        log.info("event=startup.nats_consumer_ready")
        tasks = [
            asyncio.create_task(
                run_polling_with_retries(
                    dp=dp,
                    bot=bot,
                    js=js,
                    remove_key_subject=CONFIG.nats_remove_consumer_subject,
                    allowed_updates=allowed_updates,
                    shutdown_event=shutdown_event,
                ),
                name="polling",
            ),
            asyncio.create_task(run_fastapi(bot, sessionmaker), name="fastapi"),
        ]
        wait_shutdown_task = asyncio.create_task(shutdown_event.wait(), name="shutdown_wait")
        done, pending = await asyncio.wait(
            [*tasks, wait_shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if wait_shutdown_task in done and shutdown_event.is_set():
            log.warning("event=shutdown.requested reason=signal")
        for task in done:
            if task is wait_shutdown_task:
                continue
            exc = task.exception()
            if exc is not None:
                log.error("event=runtime.task_failed task=%s", task.get_name(), exc_info=exc)
                shutdown_event.set()
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    except Exception:
        log.exception("event=runtime.fatal")
        raise
    finally:
        if wait_shutdown_task and not wait_shutdown_task.done():
            wait_shutdown_task.cancel()
            await asyncio.gather(wait_shutdown_task, return_exceptions=True)
        if scheduler.running:
            scheduler.shutdown(wait=False)
            log.info("event=scheduler.stopped")
        await nc.close()
        log.info('event=shutdown.nats_closed')
        await bot.session.close()
        log.info("event=shutdown.bot_session_closed")
        await engine_instance.dispose()
        log.info("event=shutdown.db_disposed")


async def run_fastapi(bot: Bot, session_maker:  async_sessionmaker):
    fastapi_app.state.bot = bot
    fastapi_app.state.session_maker = session_maker
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=8888,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()
