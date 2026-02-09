import logging
import asyncio
from typing import Optional

from aiogram import Bot, html
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from bot.database.methods.get import get_all_location
from bot.database.methods.update import server_auto_work_update, server_space_update
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
            # limit concurrency of server checks and apply timeout from CONFIG
            sem = asyncio.Semaphore(CONFIG.server_check_concurrency)
            for location in all_locations:
                await check_space_server(bot, location, session)
                await check_work_location(bot, session, location, sem)
    except Exception as e:
        log.error(f"Error in server_control_manager: {e}", exc_info=True)
    finally:
        log.info("Server control check completed")


async def check_work_location(
    bot: Bot,
    session: AsyncSession,
    location: Location,
    sem: asyncio.Semaphore
):
    for vds in location.vds:
        servers = list(vds.servers)

        async def _network_check(server: Servers):
            # perform network-only check under semaphore and timeout
            async def _fetch():
                manager = ServerManager(server)
                await manager.login()
                return await manager.get_all_user()

            await sem.acquire()
            try:
                try:
                    users = await asyncio.wait_for(
                        _fetch(),
                        timeout=CONFIG.server_check_timeout_sec
                    )
                except asyncio.TimeoutError:
                    log.warning(
                        "Timeout while checking server id=%s ip=%s",
                        server.id,
                        getattr(server, 'ip', getattr(server, 'host', None))
                    )
                    return (server, None)
                except Exception as e:
                    log.error(
                        "Error during network check for server id=%s ip=%s: %s",
                        server.id,
                        getattr(server, 'ip', getattr(server, 'host', None)),
                        e,
                        exc_info=True
                    )
                    return (server, None)

                return (server, users)
            finally:
                try:
                    sem.release()
                except Exception:
                    pass

        # launch network checks concurrently (bounded by semaphore)
        tasks = [asyncio.create_task(_network_check(s)) for s in servers]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # process results sequentially using the DB session
        for server, users in results:
            server_work = False
            if users is not None:
                try:
                    space = len(users)
                    await server_space_update(session, server.id, space)
                    server_work = True
                except Exception as e:
                    log.error(
                        "Failed to update server space for id=%s: %s",
                        server.id,
                        e,
                        exc_info=True
                    )

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
    location: Location,
    session: AsyncSession
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


async def check_work_server(server: Servers, session: AsyncSession, sem: asyncio.Semaphore) -> bool:
    """Проверяет, может ли сервер вернуть список пользователей.

    При успешном подключении обновляет actual_space на основе количества пользователей.
    Uses a semaphore to limit concurrent checks and `asyncio.wait_for` to bound
    the time spent on login+fetch. Any timeout/exception marks the server as
    not working for this iteration without crashing the manager.
    """
    async def _fetch_users():
        server_manager = ServerManager(server)
        await server_manager.login()
        return await server_manager.get_all_user()

    await sem.acquire()
    try:
        try:
            all_user_server = await asyncio.wait_for(
                _fetch_users(),
                timeout=CONFIG.server_check_timeout_sec
            )
        except asyncio.TimeoutError:
            log.warning(
                "Timeout while checking server id=%s type=%s",
                server.id,
                getattr(server, "type_vpn", None)
            )
            return False

        if all_user_server is None:
            return False

        # Update server space based on current user count
        space = len(all_user_server)
        await server_space_update(session, server.id, space)
        return True

    except Exception as e:
        log.error(f"Error checking server {server.id}: {e}", exc_info=True)
        return False
    finally:
        try:
            sem.release()
        except Exception:
            pass


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
