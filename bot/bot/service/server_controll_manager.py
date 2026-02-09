import logging

from aiogram import Bot, html
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from bot.database.methods.get import get_all_location
from bot.database.methods.update import server_auto_work_update
from bot.database.models.main import Location, Servers
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.language import Localization
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

_ = Localization.text


async def server_control_manager(
    bot: Bot,
    session_pool: async_sessionmaker,
) -> None:
    """Управляет проверкой и контролем состояния серверов во всех локациях."""
    try:
        async with session_pool() as session:
            all_locations = await get_all_location(session)
            for location in all_locations:
                await check_space_server(bot, location)
                await check_work_location(bot, session, location)
    except Exception as e:
        log.error(f"Error in server_control_manager: {e}", exc_info=True)
    finally:
        log.info("Server control check completed")


async def check_work_location(
    bot: Bot,
    session: AsyncSession,
    location: Location
):
    for vds in location.vds:
        for server in vds.servers:
            server_work = await check_work_server(server)
            if server_work:
                await handle_working_server(
                    bot, session, server, location.name, vds.ip
                )
            else:
                await handle_non_working_server(
                    bot, session, server, location.name, vds.ip
                )


async def check_space_server(
    bot: Bot,
    location: Location
):
    for vds in location.vds:
        sum_actual_space = 0
        for server in vds.servers:
            sum_actual_space += server.actual_space
        if sum_actual_space >= vds.max_space - CONFIG.alert_server_space:
            text = _('space_message', CONFIG.languages).format(
                vds_ip=html.quote(vds.ip),
                locale_name=html.quote(location.name),
                actual_space=sum_actual_space,
                max_spase=vds.max_space,
            )
            await notify_admin(bot, text)


async def check_work_server(server: Servers) -> bool:
    """Проверяет, может ли сервер вернуть список пользователей."""
    try:
        server_manager = ServerManager(server)
        await server_manager.login()
        all_user_server = await server_manager.get_all_user()
        return all_user_server is not None
    except Exception as e:
        log.error(f"Error checking server {server.id}: {e}", exc_info=True)
        return False


async def handle_working_server(
    bot: Bot,
    session: AsyncSession,
    server: Servers,
    location_name: str,
    vds_ip: str
) -> None:
    """Обрабатывает рабочий сервер."""
    if not server.auto_work:
        await server_auto_work_update(session, server.id, True)
        await notify_admin(
            bot,
            _('message_server_auto_show', CONFIG.languages).format(
                type_vpn=ServerManager.VPN_TYPES.get(server.type_vpn).NAME_VPN,
                vds_ip=html.quote(str(vds_ip)),
                location_name=html.quote(location_name)
            )
        )


async def handle_non_working_server(
    bot: Bot,
    session: AsyncSession,
    server: Servers,
    location_name: str,
    vds_ip: str
) -> None:
    """Обрабатывает нерабочий сервер."""
    if server.auto_work:
        await server_auto_work_update(session, server.id, False)
        await notify_admin(
            bot,
            _('message_server_auto_hidden', CONFIG.languages).format(
                type_vpn=ServerManager.VPN_TYPES.get(server.type_vpn).NAME_VPN,
                vds_ip=html.quote(str(vds_ip)),
                location_name=html.quote(location_name)
            )
        )


async def notify_admin(bot: Bot, message: str) -> None:
    """Отправляет уведомление администратору."""
    try:
        await bot.send_message(
            chat_id=CONFIG.admin_tg_id,
            text=message
        )
    except Exception as e:
        log.error(f"Error sending notification to admin: {e}", exc_info=True)
