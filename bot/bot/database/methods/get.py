import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload, outerjoin, aliased
from sqlalchemy import and_, select, func, desc, exists, RowMapping, case

from bot.database.models.main import (
    Persons,
    Servers,
    Payments,
    StaticPersons,
    PromoCode,
    WithdrawalRequests,
    Groups,
    Donate,
    Keys,
    message_button_association,
    Location,
    Vds, Metric
)
from bot.misc.util import CONFIG


def person_cache_key(telegram_id):
    return f"person:{telegram_id}"


def person_id_cache_key(list_input):
    return f"person:{list_input}"


async def get_person(session: AsyncSession, telegram_id):
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).filter(Persons.tgid == telegram_id)
    result = await session.execute(statement)
    person = result.unique().scalar_one_or_none()
    return person


async def get_person_id(session: AsyncSession, list_input):
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).filter(Persons.tgid.in_(list_input))
    result = await session.execute(statement)
    persons = result.unique().scalars().all()
    return persons


async def get_keys_id(session: AsyncSession, list_input):
    statement = select(Keys).options(
        joinedload(Keys.person),
    ).filter(Keys.id.in_(list_input))
    result = await session.execute(statement)
    keys = result.unique().scalars().all()
    return keys


async def get_keys_tg_ids(session: AsyncSession, list_input):
    statement = select(Keys).options(
        joinedload(Keys.person),
    ).filter(Keys.user_tgid.in_(list_input))
    result = await session.execute(statement)
    keys = result.unique().scalars().all()
    return keys


async def _get_person(session, telegram_id):
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).filter(Persons.tgid == telegram_id)
    result = await session.execute(statement)
    person = result.unique().scalar_one_or_none()
    return person


async def _get_server(session, id_server) -> Servers:
    statement = select(Servers).options(
        joinedload(Servers.vds_table)
    ).filter(Servers.id == id_server)
    result = await session.execute(statement)
    return result.unique().scalar_one_or_none()


async def get_all_donate(session: AsyncSession):
    statement = select(Donate)
    result = await session.execute(statement)
    persons = result.scalars().all()
    return persons


async def get_all_user(session: AsyncSession):
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).order_by(Persons.id)
    result = await session.execute(statement)
    persons = result.unique().scalars().all()
    return persons


async def get_all_subscription(session: AsyncSession):
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).filter(Persons.keys.any()).order_by(Persons.id)
    result = await session.execute(statement)
    persons = result.unique().scalars().all()
    return persons


async def get_no_subscription(session: AsyncSession):
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).filter(~Persons.keys.any()).order_by(Persons.id)
    result = await session.execute(statement)
    persons = result.unique().scalars().all()
    return persons


async def get_payments(session: AsyncSession):
    statement = select(Payments).options(
        joinedload(Payments.payment_id)
    ).order_by(Payments.id)
    result = await session.execute(statement)
    payments = result.scalars().all()

    for payment in payments:
        payment.user = payment.payment_id.username

    return payments


async def get_payment(session: AsyncSession, id_payment):
    statement = select(Payments).options(
        joinedload(Payments.payment_id)
    ).filter(Payments.id_payment == id_payment).order_by(
        desc(Payments.data)
    )
    result = await session.execute(statement)
    payments = result.scalars().first()
    return payments


async def get_server(session: AsyncSession, id_server):
    return await _get_server(session, id_server)


async def get_server_id(session: AsyncSession, id_server) -> Servers:
    statement = select(Servers).options(
        joinedload(Servers.vds_table)
        .joinedload(Vds.location_table)
    ).filter(Servers.id == id_server)
    result = await session.execute(statement)
    server = result.scalar_one_or_none()
    return server


async def get_type_vpn(session: AsyncSession, group_name):
    result = await session.execute(
        select(Servers.type_vpn).join(Servers.vds_table).join(
            Vds.location_table)
        .filter(
            and_(
                Location.work == True, # noqa
                Location.group == group_name,
                Vds.work == True, # noqa
                Servers.work == True, # noqa
                Servers.auto_work == True,  # noqa
                Servers.free_server == False # noqa
            )
        ).distinct()
    )
    unique_type_vpn = result.scalars().all()
    return unique_type_vpn


async def get_free_server_id(session: AsyncSession, id_location, type_vpn):
    statement = select(Servers).join(Servers.vds_table).join(
        Vds.location_table).filter(
        Location.id == id_location,
        Servers.type_vpn == type_vpn,
        Location.work == True,  # noqa
        Vds.work == True,  # noqa
        Servers.work == True,  # noqa
        Servers.auto_work == True,  # noqa
        Servers.actual_space < Vds.max_space,
        Servers.free_server == False  # noqa
    ).options(
        selectinload(Servers.vds_table).selectinload(Vds.location_table)
    ).order_by(Servers.actual_space)
    result = await session.execute(statement)
    server = result.unique().scalars().all()
    if len(server) != 0:
        return server[0]
    else:
        return None


async def get_name_location_server(session: AsyncSession, server_id):
    statement = select(Servers).join(Servers.vds_table).join(
        Vds.location_table).filter(
        Servers.id == server_id
    ).options(
        selectinload(Servers.vds_table).selectinload(Vds.location_table)
    ).order_by(Servers.actual_space)
    result = await session.execute(statement)
    server = result.unique().scalar_one_or_none()
    return server.vds_table.location_table.name


async def get_free_servers(session: AsyncSession, group_name, type_vpn):
    base_query = select(Location).join(Location.vds).join(
        Vds.servers).filter(
        and_(
            Location.work == True, # noqa
            Vds.work == True, # noqa
            Servers.work == True, # noqa
            Servers.auto_work == True,  # noqa
            Servers.actual_space < Vds.max_space,
            Location.group == group_name,
            Servers.type_vpn == type_vpn,
            Servers.free_server == False
        )
    ).options(
        selectinload(Location.vds).selectinload(Vds.servers)
    ).order_by(Servers.actual_space)
    result = await session.execute(base_query)
    locations = result.unique().scalars().all()
    if not locations:
        raise FileNotFoundError('Server not found')
    return locations


async def get_free_vpn_server(session: AsyncSession):
    statement = select(Servers).join(Servers.vds_table).join(
        Vds.location_table).filter(
        Location.work == True,  # noqa
        Vds.work == True,  # noqa
        Servers.work == True,  # noqa
        Servers.auto_work == True,  # noqa
        Servers.free_server == True, # noqa
        Servers.actual_space < Vds.max_space,
    ).options(
        selectinload(Servers.vds_table).selectinload(Vds.location_table)
    ).order_by(Servers.actual_space)
    result = await session.execute(statement)
    server = result.unique().scalars().first()
    return server


async def get_all_location(session: AsyncSession) ->  Sequence[Location]:
    base_query = select(Location).join(Location.vds).join(
        Vds.servers
    ).options(
        selectinload(Location.vds).selectinload(Vds.servers)
    ).order_by(Servers.actual_space)
    result = await session.execute(base_query)
    locations = result.unique().scalars().all()
    return locations


async def get_all_static_user(session: AsyncSession):
    statement = select(StaticPersons).options(
        joinedload(StaticPersons.server_table)
    )
    result = await session.execute(statement)
    all_static_user = result.scalars().all()
    return all_static_user


async def get_static_user(
    session: AsyncSession,
    name_user: str
) -> StaticPersons:
    statement = select(StaticPersons).where(StaticPersons.name == name_user)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_all_promo_code(session: AsyncSession):
    statement = select(PromoCode).options(
        joinedload(PromoCode.person)
    )
    result = await session.execute(statement)
    promo_code = result.unique().scalars().all()
    return promo_code


async def get_promo_codes_user(session: AsyncSession, telegram_id):
    statement = select(PromoCode).join(
        message_button_association,
        PromoCode.id == message_button_association.c.promocode_id
    ).join(
        Persons, Persons.id == message_button_association.c.users_id
    ).filter(
        Persons.tgid == telegram_id,
        message_button_association.c.use == False # noqa
    )
    result = await session.execute(statement)
    promo_codes = result.scalars().all()
    return promo_codes


async def get_promo_code(session: AsyncSession, text_promo) -> PromoCode:
    promo_code_query = select(PromoCode).where(
        PromoCode.text == text_promo)
    promo_code_result = await session.execute(promo_code_query)
    promo_code = promo_code_result.scalar_one_or_none()

    if not promo_code:
        return None

    usage_count_query = (
        select(func.count(message_button_association.c.users_id))
        .where(message_button_association.c.promocode_id == promo_code.id)
    )
    usage_count_result = await session.execute(usage_count_query)
    usage_count = usage_count_result.scalar()

    if usage_count < promo_code.count_use:
        return promo_code
    else:
        return None


async def get_count_referral_user(session: AsyncSession, telegram_id):
    statement = select(func.count(Persons.id)).filter(
        Persons.referral_user_tgid == telegram_id
    )
    result = await session.execute(statement)
    return result.scalar()


async def get_referral_balance(session: AsyncSession, telegram_id):
    statement = select(Persons).filter(Persons.tgid == telegram_id)
    result = await session.execute(statement)
    person = result.scalar_one_or_none()
    return person.referral_balance


async def get_all_application_referral(session: AsyncSession):
    statement = select(WithdrawalRequests)
    result = await session.execute(statement)
    return result.scalars().all()


async def get_application_referral_check_false(session: AsyncSession):
    statement = select(WithdrawalRequests).filter(
        WithdrawalRequests.check_payment == False # noqa
    )
    result = await session.execute(statement)
    return result.scalars().all()


async def get_person_lang(session: AsyncSession, telegram_id):
    statement = select(Persons).filter(Persons.tgid == telegram_id)
    result = await session.execute(statement)
    person = result.scalar_one_or_none()
    if person is None:
        return CONFIG.languages
    return person.lang


async def get_all_groups(session: AsyncSession):
    statement = select(
        Groups, func.count(Groups.users), func.count(Groups.locations)). \
        outerjoin(Groups.users). \
        outerjoin(Groups.locations). \
        group_by(Groups.id). \
        order_by(Groups.id)
    result = await session.execute(statement)
    rows = result.all()
    groups_with_counts = []
    for row in rows:
        group = row[0]
        count_user = row[1]
        count_server = row[2]
        groups_with_counts.append(
            {"group": group, "count_user": count_user,
             "count_server": count_server})
    return groups_with_counts


async def get_group(session: AsyncSession, group_id):
    statement = select(Groups).filter(Groups.id == group_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_group_name(session: AsyncSession, group_name):
    statement = select(Groups).filter(Groups.name == group_name)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_users_group(session: AsyncSession, group_id):
    statement = select(Groups).filter(Groups.id == group_id)
    result = await session.execute(statement)
    group = result.scalar_one_or_none()
    statement = select(Persons).options(
        joinedload(Persons.keys)
    ).filter(Persons.group == group.name).order_by(Persons.id) # noqa
    result = await session.execute(statement)
    return result.unique().scalars().all()


async def get_count_groups(session: AsyncSession):
    statement = select(func.count(Groups.id))
    result = await session.execute(statement)
    count = result.scalar_one()
    return count


async def get_key_user(session: AsyncSession, telegram_id, free_key=False):
    statement = select(Keys).options(
        joinedload(Keys.server_table)
        .joinedload(Servers.vds_table)
        .joinedload(Vds.location_table)
    ).filter(
        Keys.user_tgid == telegram_id,
        Keys.free_key == free_key # noqa
    )
    result = await session.execute(statement)
    if free_key:
        return result.unique().scalar_one_or_none()
    else:
        return result.unique().scalars().all()


async def get_key_id(session: AsyncSession, key_id) -> Keys:
    statement = select(Keys).options(
        joinedload(Keys.server_table)
    ).filter(
        Keys.id == key_id
    )
    result = await session.execute(statement)
    key = result.unique().scalar_one_or_none()
    return key


async def get_key_id_server(session: AsyncSession, telegram_id, server_id):
    statement = select(Keys).options(
        joinedload(Keys.server_table)
    ).filter(
        Keys.server == server_id,
        Keys.user_tgid == telegram_id
    )
    result = await session.execute(statement)
    key = result.unique().scalar_one_or_none()
    return key


async def get_all_locations(session: AsyncSession):
    statement = select(Location).options(
        joinedload(Location.vds)
    )
    result = await session.execute(statement)
    locations = result.unique().scalars().all()
    return locations


async def get_location_id(session: AsyncSession, id_location):
    statement = select(Location).filter(Location.id == id_location)
    result = await session.execute(statement)
    location = result.scalar_one_or_none()
    return location


async def get_vds_id(session: AsyncSession, id_vds):
    statement = select(Vds).options(
        joinedload(Vds.servers)
    ).filter(Vds.id == id_vds)
    result = await session.execute(statement)
    location = result.unique().scalar_one_or_none()
    return location


async def get_vds_ip(session: AsyncSession, ip):
    statement = select(Vds).filter(Vds.ip == ip)
    result = await session.execute(statement)
    location = result.unique().scalar_one_or_none()
    return location


async def get_vds_location(session: AsyncSession, id_location):
    statement = select(Vds).options(
        joinedload(Vds.servers)
    ).filter(Vds.location == id_location)
    result = await session.execute(statement)
    locations = result.unique().scalars().all()
    return locations


async def get_all_metric(session: AsyncSession) -> Sequence[Metric]:
    statement = select(Metric).options(
        joinedload(Metric.users)
    )
    result = await session.execute(statement)
    all_metric = result.unique().scalars().all()
    return all_metric


async def get_metric(session: AsyncSession, id_metric) -> Metric:
    statement = select(Metric).filter(Metric.id == id_metric).options(
        joinedload(Metric.users)
    )
    result = await session.execute(statement)
    metric = result.unique().scalar_one_or_none()
    return metric


async def get_metric_code(session: AsyncSession, code) -> Metric:
    statement = select(Metric).filter(Metric.code == code).options(
        joinedload(Metric.users)
    )
    result = await session.execute(statement)
    metric = result.unique().scalar_one_or_none()
    return metric


async def get_users_trial_metric(
    session: AsyncSession,
    id_metric: int
) -> Sequence[Persons]:
    statement = select(Persons).filter(
        Persons.metric == id_metric, Persons.trial_period == True
    )
    result = await session.execute(statement)
    users = result.unique().scalars().all()
    return users


async def get_users_payments_metric(
    session: AsyncSession,
    id_metric: int
) -> Sequence[Payments]:
    statement = select(Payments).join(Payments.payment_id).filter(
        Persons.metric == id_metric,
    ).options(
        selectinload(Payments.payment_id)
    ).order_by(Payments.id)
    result = await session.execute(statement)
    payments = result.scalars().all()
    return payments


async def get_users_payments_tariff_metric(
    session: AsyncSession,
    id_metric: int
) -> Sequence[dict]:
    statement = select(
        Payments.amount,
        func.count(Payments.amount).label('user_count')
    ).join(Persons).filter(
        Persons.metric == id_metric,
    ).group_by(
        Payments.amount
    ).order_by(
        Payments.amount
    )
    result = await session.execute(statement)
    grouped_payments = result.all()
    return [
        {"amount": row.amount, "user_count": row.user_count}
        for row in grouped_payments
    ]


async def get_paying_users_count(
    session: AsyncSession,
    id_metric: int
) -> int:
    statement = select(
        func.count(Payments.user.distinct())
    ).join(Persons).filter(
        Persons.metric == id_metric
    )
    result = await session.execute(statement)
    paying_users_count = result.scalar()
    return paying_users_count


async def get_metric_stats(session: AsyncSession) ->  Sequence[RowMapping]:
    statement = select(
        Metric.text,
        Metric.code,
        (
            select(func.count(Persons.id))
            .where(Persons.metric == Metric.id)
            .correlate(Metric)
            .scalar_subquery()
        ).label('users_count'),
        (
            select(func.count(Persons.id))
            .where(and_(
                Persons.metric == Metric.id,
                Persons.trial_period == True
            ))
            .correlate(Metric)
            .scalar_subquery()
        ).label('trial_started'),
        (
            select(func.count(Persons.id))
            .where(and_(
                Persons.metric == Metric.id,
                Persons.trial_period == True,
                ~exists().where(and_(
                    Keys.user_tgid == Persons.tgid,
                    Keys.trial_period == True
                ))
            ))
            .correlate(Metric)
            .scalar_subquery()
        ).label('trial_ended'),
        (
            select(func.count(Persons.id))
            .where(and_(
                Persons.metric == Metric.id,
                exists().where(Payments.user == Persons.id)
            ))
            .correlate(Metric)
            .scalar_subquery()
        ).label('subscribed'),
        (
            select(func.count(Persons.id))
            .where(and_(
                Persons.metric == Metric.id,
                exists().where(Payments.user == Persons.id),
                ~exists().where(Keys.user_tgid == Persons.tgid)
            ))
            .correlate(Metric)
            .scalar_subquery()
        ).label('subscription_ended')
    )

    result = await session.execute(statement)
    metrics_data = result.mappings().all()
    return metrics_data


async def dump_postgres_db():
    dump_dir = Path("/app/logs/db_dumps")
    dump_dir.mkdir(parents=True, exist_ok=True)
    output_file = dump_dir / 'BotDataBase.dump'
    process = await asyncio.create_subprocess_exec(
        'pg_dump',
        '-U', CONFIG.postgres_user,
        '-h', 'db_postgres',
        '-d', CONFIG.postgres_db,
        '-F', 'c',
        '-f', str(output_file),
        env={**os.environ, 'PGPASSWORD': CONFIG.postgres_password},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        logging.info(f"[✅] Dump completed successfully: {output_file}")
    else:
        logging.info(f"[❌] Error during dump:\n{stderr.decode()}")


async def get_ref_bord(session: AsyncSession) -> Sequence[RowMapping]:
    Referrer = aliased(Persons)

    stmt = select(
        Referrer.tgid.label('id'),
        Referrer.username.label('username'),
        func.count(Persons.id).label('users_count'),
        func.sum(case((Persons.trial_period == True, 1), else_=0)).label(
            'trial_started'),
        func.sum(case((
            and_(
                Persons.trial_period == True,
                ~exists().where(and_(
                    Keys.user_tgid == Persons.tgid,
                    Keys.trial_period == True,
                    Keys.subscription > int(datetime.now().timestamp())
                ))
            ), 1), else_=0)).label('trial_ended'),
        func.sum(case((
            exists().where(and_(
                Payments.user == Persons.id,
            )), 1), else_=0)).label('subscribed'),
        func.sum(case((
            and_(
                exists().where(and_(
                    Payments.user == Persons.id,
                )),
                ~exists().where(and_(
                    Keys.user_tgid == Persons.tgid,
                    Keys.subscription > int(datetime.now().timestamp())
                ))
            ), 1), else_=0)).label('subscription_ended')
    ).select_from(
        Persons
    ).join(
        Referrer,
        Referrer.tgid == Persons.referral_user_tgid
    ).where(
        Persons.referral_user_tgid.isnot(None)
    ).group_by(
        Referrer.tgid,
        Referrer.username
    ).order_by(
        desc('users_count')
    )
    result = await session.execute(stmt)
    return result.mappings().all()


async def get_user_tg_ids_by_wg_keys(session, wg_public_keys: list):
    """
    Получает список user_tgid по списку wg_public_key

    Args:
        session: SQLAlchemy сессия
        wg_public_keys: список публичных ключей WireGuard
    Returns:
        list: список user_tgid
    """
    query = (
        select(Keys.user_tgid)
        .where(Keys.wg_public_key.in_(wg_public_keys))
    )
    result = await session.execute(query)
    user_tg_ids = [row[0] for row in result.all()]
    return user_tg_ids
