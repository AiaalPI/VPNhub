from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.database.models.main import Keys, Persons
from bot.services.migration_service import (
    MIGRATION_STATUS_MIGRATED,
    is_legacy_backend_type,
)
from bot.misc.util import CONFIG


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _has_active_key_of_type(user: Persons, checker) -> bool:
    now_ts = _now_ts()
    for key in user.keys:
        if int(getattr(key, "subscription", 0) or 0) <= now_ts:
            continue
        server = getattr(key, "server_table", None)
        if server is None:
            continue
        if checker(int(getattr(server, "type_vpn", -1))):
            return True
    return False


def _has_active_legacy(user: Persons) -> bool:
    return _has_active_key_of_type(user, is_legacy_backend_type)


def _has_active_marzban(user: Persons) -> bool:
    return _has_active_key_of_type(
        user,
        lambda type_vpn: type_vpn == CONFIG.TypeVpn.MARZBAN.value,
    )


async def _get_all_users_with_keys(session: AsyncSession) -> list[Persons]:
    result = await session.execute(
        select(Persons)
        .options(joinedload(Persons.keys).joinedload(Keys.server_table))
        .where(Persons.blocked.is_(False))
        .order_by(Persons.id)
    )
    return result.unique().scalars().all()


async def get_users_on_old_3xui(session: AsyncSession) -> int:
    users = await _get_all_users_with_keys(session)
    return sum(1 for user in users if _has_active_legacy(user))


async def get_users_migrated_to_marzban(session: AsyncSession) -> int:
    users = await _get_all_users_with_keys(session)
    return sum(
        1
        for user in users
        if (
            (user.migration_status or "").strip().lower() == MIGRATION_STATUS_MIGRATED
            or _has_active_marzban(user)
        )
    )


async def get_users_still_using_old_system(session: AsyncSession) -> int:
    users = await _get_all_users_with_keys(session)
    return sum(
        1
        for user in users
        if _has_active_legacy(user) and not _has_active_marzban(user)
    )


@dataclass(slots=True)
class MigrationStats:
    users_on_old_3xui: int
    users_migrated_to_marzban: int
    users_still_using_old_system: int


async def get_migration_stats(session: AsyncSession) -> MigrationStats:
    return MigrationStats(
        users_on_old_3xui=await get_users_on_old_3xui(session),
        users_migrated_to_marzban=await get_users_migrated_to_marzban(session),
        users_still_using_old_system=await get_users_still_using_old_system(session),
    )
