from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Location, Persons, Servers, StaticPersons, Vds


def _utc_now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _count_active_users_by_location_aliases(
    session: AsyncSession,
    aliases: list[str],
) -> int:
    aliases = [a.strip().lower() for a in aliases if a.strip()]
    if not aliases:
        return 0
    location_match = or_(*[func.lower(Location.name).contains(alias) for alias in aliases])
    value = await session.scalar(
        select(func.count(func.distinct(Keys.user_tgid)))
        .join(Keys.server_table)
        .join(Servers.vds_table)
        .join(Vds.location_table)
        .join(Persons, Persons.tgid == Keys.user_tgid)
        .where(
            Persons.blocked.is_(False),
            Keys.subscription > _utc_now_ts(),
            location_match,
        )
    )
    return int(value or 0)


async def get_finland_users(session: AsyncSession) -> int:
    return await _count_active_users_by_location_aliases(
        session,
        ["finland", "финлянд"],
    )


async def get_poland_users(session: AsyncSession) -> int:
    return await _count_active_users_by_location_aliases(
        session,
        ["poland", "польш", "warsaw", "варшав"],
    )


@dataclass(slots=True)
class ServerStats:
    finland_users: int
    poland_users: int
    total_locations: int
    active_locations: int
    total_vds: int
    active_vds: int
    total_protocols: int
    active_protocols: int
    hidden_protocols: int
    static_users: int


async def get_server_stats(session: AsyncSession) -> ServerStats:
    total_locations = int(
        await session.scalar(select(func.count(Location.id))) or 0
    )
    active_locations = int(
        await session.scalar(
            select(func.count(Location.id)).where(Location.work.is_(True))
        ) or 0
    )
    total_vds = int(await session.scalar(select(func.count(Vds.id))) or 0)
    active_vds = int(
        await session.scalar(
            select(func.count(Vds.id)).where(Vds.work.is_(True))
        ) or 0
    )
    total_protocols = int(await session.scalar(select(func.count(Servers.id))) or 0)
    active_protocols = int(
        await session.scalar(
            select(func.count(Servers.id)).where(
                Servers.work.is_(True),
                Servers.auto_work.is_(True),
            )
        ) or 0
    )
    hidden_protocols = int(
        await session.scalar(
            select(func.count(Servers.id)).where(
                Servers.work.is_(True),
                Servers.auto_work.is_(False),
            )
        ) or 0
    )
    static_users = int(
        await session.scalar(select(func.count(StaticPersons.id))) or 0
    )
    return ServerStats(
        finland_users=await get_finland_users(session),
        poland_users=await get_poland_users(session),
        total_locations=total_locations,
        active_locations=active_locations,
        total_vds=total_vds,
        active_vds=active_vds,
        total_protocols=total_protocols,
        active_protocols=active_protocols,
        hidden_protocols=hidden_protocols,
        static_users=static_users,
    )
