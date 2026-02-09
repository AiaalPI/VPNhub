import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import (
    Servers,
    StaticPersons,
    PromoCode,
    Groups,
    Keys,
    Location,
    Vds, Metric, NotRemoveKey
)


async def delete_server(session: AsyncSession, id_server):
    statement = select(Servers).filter(Servers.id == id_server)
    result = await session.execute(statement)
    server = result.scalar_one_or_none()
    if server is not None:
        await session.delete(server)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_static_user_bd(session: AsyncSession, name):
    statement = select(StaticPersons).filter(StaticPersons.name == name)
    result = await session.execute(statement)
    static_user = result.scalar_one_or_none()
    if static_user is not None:
        await session.delete(static_user)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_promo_code(session: AsyncSession, id_promo):
    statement = select(PromoCode).filter(PromoCode.id == id_promo)
    result = await session.execute(statement)
    promo_code = result.scalar_one_or_none()
    if promo_code is not None:
        await session.delete(promo_code)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_group(session: AsyncSession, group_id):
    statement = select(Groups).filter(Groups.id == group_id)
    result = await session.execute(statement)
    group = result.scalar_one_or_none()
    if group is not None:
        await session.delete(group)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_key_in_user(session: AsyncSession, key_id):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        logging.info(f'Deleted key user {key.user_tgid}')
        await session.delete(key)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_location(session: AsyncSession, location_id):
    statement = select(Location).filter(Location.id == location_id)
    result = await session.execute(statement)
    location = result.scalar_one_or_none()
    if location is not None:
        await session.delete(location)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_vds(session: AsyncSession, vds_id):
    statement = select(Vds).filter(Vds.id == vds_id)
    result = await session.execute(statement)
    vds = result.scalar_one_or_none()
    if vds is not None:
        await session.delete(vds)
        await session.commit()
    else:
        raise ModuleNotFoundError


async def delete_metric_id(session: AsyncSession,metric_id: int):
    statement = select(Metric).filter(Metric.id == metric_id)
    result = await session.execute(statement)
    metric = result.scalar_one_or_none()
    await session.delete(metric)
    await session.commit()


async def delete_not_keys(
    session: AsyncSession,
    name_key: str,
    key_id: int,
    server_id: int
):
    statement = select(NotRemoveKey).where(
        and_(
            NotRemoveKey.name_key == name_key,
            NotRemoveKey.key_id == key_id,
            NotRemoveKey.server_id == server_id
        )
    )
    result = await session.execute(statement)
    keys = result.scalars().all()
    for key in keys:
        await session.delete(key)
    if len(keys) != 0:
        await session.commit()
    return True