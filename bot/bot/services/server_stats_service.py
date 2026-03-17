from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys, Location, Persons, Servers, Vds


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


async def get_japan_users(session: AsyncSession) -> int:
    return await _count_active_users_by_location_aliases(
        session,
        ["japan", "япони", "tokyo", "токио"],
    )


@dataclass(slots=True)
class ServerStats:
    finland_users: int
    japan_users: int


async def get_server_stats(session: AsyncSession) -> ServerStats:
    return ServerStats(
        finland_users=await get_finland_users(session),
        japan_users=await get_japan_users(session),
    )
