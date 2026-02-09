import asyncio
import logging
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
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
from bot.misc.commands import set_commands
from bot.misc.loop import loop
from bot.misc.nats_connect import connect_to_nats
from bot.misc.start_consumers import start_delayed_consumer
from bot.misc.util import CONFIG
from bot.service.send_dump import send_dump
from bot.service.server_controll_manager import server_control_manager
from bot.webhooks import app as fastapi_app


async def start_bot():
    bot = Bot(
        token=CONFIG.tg_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    nc, js = await connect_to_nats(servers=CONFIG.nats_servers)

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
        logging.info('Import BD successfully -- OK')
        return
    sessionmaker = async_sessionmaker(
        engine(),
        expire_on_commit=False
    )
    dp.update.outer_middleware(DbSessionMiddleware(sessionmaker))
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    await set_commands(bot)
    scheduler.add_job(
        loop,
        "interval",
        seconds=15,
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

    try:
        await asyncio.gather(
            dp.start_polling(
                bot,
                js=js,
                remove_key_subject=CONFIG.nats_remove_consumer_subject
            ),
            start_delayed_consumer(
                nc=nc,
                js=js,
                bot=bot,
                session_pool=sessionmaker,
                subject=CONFIG.nats_remove_consumer_subject,
                stream=CONFIG.nats_remove_consumer_stream,
                durable_name=CONFIG.nats_remove_consumer_durable_name
            ),
            run_fastapi(bot, sessionmaker)
        )
    except Exception as e:
        logging.error(e)
    finally:
        await nc.close()
        logging.info('Connection to NATS closed')


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
