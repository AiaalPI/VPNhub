import datetime
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import _get_person, get_metric_code
from bot.database.models.main import (
    Persons,
    Payments,
    StaticPersons,
    PromoCode,
    WithdrawalRequests,
    Groups,
    Keys,
    Donate, Metric, NotRemoveKey
)
from bot.misc.util import CONFIG
from bot.service.service import generate_random_string


async def add_new_person(
    session: AsyncSession,
    from_user,
    username,
    ref_user,
    metric_id,
):
    tom = Persons(
        tgid=from_user.id,
        username=username,
        fullname=from_user.full_name,
        lang_tg=from_user.language_code or None,
        referral_user_tgid=ref_user or None,
        banned=True,
        metric=metric_id,
    )
    session.add(tom)
    await session.commit()


async def add_payment(
    session: AsyncSession,
    telegram_id,
    deposit,
    payment_system,
    id_payment=None,
    month_count=None
):
    person = await _get_person(session, telegram_id)
    if person is not None:
        payment = Payments(
            amount=deposit,
            data=datetime.datetime.now(),
            payment_system=payment_system,
            id_payment=id_payment,
            month_count=month_count
        )
        payment.user = person.id
        session.add(payment)
        await session.commit()
    logging.info(
        f'Add DB payment '
        f'amount:{deposit} '
        f'payment_system:{payment_system}'
        f'telegram_id:{telegram_id}'
        f'month_count:{month_count}'
        f'id_payment:{id_payment}'
    )


async def add_donate(session: AsyncSession, username, price):
    donate = Donate(
        username=username,
        price=price
    )
    session.add(donate)
    await session.commit()


async def add_key(
    session: AsyncSession,
    telegram_id,
    subscription,
    id_payment=None,
    free_key=False,
    trial_period=False,
    server_id=None
):
    key = Keys(
        user_tgid=telegram_id,
        subscription=int(time.time()) + subscription,
        switch_location=CONFIG.free_switch_location,
        id_payment=id_payment,
        free_key=free_key,
        trial_period=trial_period,
        server=server_id
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)
    logging.info(
        f'Add DB key '
        f'telegram_id:{telegram_id} '
        f'subscription:{subscription} '
        f'id_payment:{id_payment} '
        f'free_key:{free_key} '
        f'trial_period:{trial_period}'
    )
    return key


async def add_server(session: AsyncSession, server):
    session.add(server)
    await session.commit()


async def add_location(session: AsyncSession, location):
    session.add(location)
    await session.commit()


async def add_vds(session: AsyncSession, vds):
    session.add(vds)
    await session.commit()


async def add_static_user(session: AsyncSession, name, server):
    static_user = StaticPersons(
        name=name,
        server=server
    )
    session.add(static_user)
    await session.commit()
    await session.refresh(static_user)
    return static_user


async def add_promo(
    session: AsyncSession,
    text_promo,
    percent,
    day,
    count_use
):
    if percent != 0:
        type_promo = 1
    else:
        type_promo = 2
    promo_code = PromoCode(
        text=text_promo,
        type_promo=type_promo,
        percent=percent,
        count_days=day,
        count_use=count_use
    )
    session.add(promo_code)
    await session.commit()


async def add_withdrawal(
    session: AsyncSession,
    tgid,
    amount,
    payment_info,
    communication
):
    withdrawal = WithdrawalRequests(
        amount=amount,
        payment_info=payment_info,
        user_tgid=tgid,
        communication=communication
    )
    session.add(withdrawal)
    await session.commit()


async def add_group(session: AsyncSession, group_name):
    group = Groups(
        name=group_name
    )
    session.add(group)
    await session.commit()


async def create_metric(
    session: AsyncSession,
    text: str,
):
    check = True
    good_code = ''
    while check:
        code = await generate_random_string()
        check_metric = await get_metric_code(session, code)
        if check_metric is None:
            good_code = code
            check = False
    metric = Metric(
        text=text,
        code=good_code
    )
    session.add(metric)
    await session.flush()
    await session.commit()
    return metric


async def add_not_remove_key(
    session: AsyncSession,
    name_key: str,
    key_id: int,
    server_id: int
):
    key = NotRemoveKey(name_key=name_key, key_id=key_id, server_id=server_id)
    session.add(key)
    await session.commit()
