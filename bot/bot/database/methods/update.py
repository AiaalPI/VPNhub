import time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.database.methods.get import _get_person, _get_server
from bot.database.models.main import (
    Persons,
    WithdrawalRequests,
    Keys,
    PromoCode,
    message_button_association,
    Location,
    Vds,
    StaticPersons,
    Servers
)
from bot.service.sync_expire_key import sinc_time


async def reduce_balance_person(session: AsyncSession, deposit, tgid):
    person = await _get_person(session, tgid)
    if person is not None:
        person.balance -= int(deposit)
        await session.commit()
        return True
    return False

async def reduce_referral_balance_person(session: AsyncSession, amount, tgid):
    person = await _get_person(session, tgid)
    if person is not None:
        person.referral_balance -= int(amount)
        if person.referral_balance < 0:
            return False
        await session.commit()
        return True
    return False


async def add_referral_balance_person(session: AsyncSession, amount, tgid):
    person = await _get_person(session, tgid)
    if person is not None:
        person.referral_balance += int(amount)
        await session.commit()
        return True
    return False


async def add_time_person(session: AsyncSession, tgid, count_time):
    person = await _get_person(session, tgid)
    if person is not None:
        now_time = int(time.time()) + count_time
        if person.banned:
            person.subscription = int(now_time)
            person.banned = False
        else:
            person.subscription += count_time
        await session.commit()
        return True
    return False


async def person_trial_period(session: AsyncSession, telegram_id):
    person = await _get_person(session, telegram_id)
    if person is not None:
        if not person.trial_period:
            person.banned = False
            person.trial_period = True
        else:
            return
        await session.commit()
        return True
    return False


async def person_special_off(session: AsyncSession, telegram_id):
    person = await _get_person(session, telegram_id)
    if person is not None:
        person.special_offer = False
        await session.commit()
        return True
    return False


async def person_banned_true(session: AsyncSession, tgid):
    person = await _get_person(session, tgid)
    if person is not None:
        person.banned = True
        person.notion_oneday = False
        person.subscription = int(time.time())
        await session.commit()
        return True
    return False


async def key_one_day_true(session: AsyncSession, key_id):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        key.notion_oneday = True
        await session.commit()
        return True
    return False


async def update_key_wg(session: AsyncSession, key_id, wg_public_key):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        key.wg_public_key = wg_public_key
        await session.commit()
        return True
    return False


async def update_static_wg(session: AsyncSession, static_id, wg_public_key):
    statement = select(StaticPersons).filter(StaticPersons.id == static_id)
    result = await session.execute(statement)
    static_person = result.scalar_one_or_none()
    if static_person is not None:
        static_person.wg_public_key = wg_public_key
        await session.commit()
        return True
    return False


async def person_delete_server(session: AsyncSession, telegram_id):
    person = await _get_person(session, telegram_id)
    if person and person.keys:
        for key in person.keys:
            await session.delete(key)
        await session.commit()
        return True
    else:
        return False


async def update_server_key(
    session: AsyncSession,
    key_id,
    server_id=None,
    reset_wg_key=False
):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.unique().scalar_one_or_none()
    server = await _get_server(session, server_id)
    if key is not None:
        key.server = server_id
        key.server_table = server
        if reset_wg_key:
            key.wg_public_key = None
        await session.commit()
        return True
    return False


async def server_work_update(session: AsyncSession, id_server, work):
    server = await _get_server(session, id_server)
    if server is not None:
        server.work = work
        await session.commit()
        return True
    return False


async def server_auto_work_update(session: AsyncSession, id_server, work):
    server = await _get_server(session, id_server)
    if server is not None:
        server.auto_work = work
        await session.commit()
        return True
    return False


async def location_switch_update(
    session: AsyncSession,
    id_location,
    pay_switch
):
    statement = select(Location).filter(Location.id == id_location)
    result = await session.execute(statement)
    location = result.unique().scalar_one_or_none()
    if location is not None:
        location.pay_switch = pay_switch
        await session.commit()
        return True
    return False


async def server_space_update(session: AsyncSession, id_server, new_space):
    server = await _get_server(session, id_server)
    if server is not None:
        server.actual_space = new_space
        await session.commit()
        return True
    return False


async def add_pomo_code_person(
    session: AsyncSession,
    tgid,
    promo_code: PromoCode
):
    statement = select(Persons).options(
        joinedload(Persons.promocode)).filter(Persons.tgid == tgid)
    result = await session.execute(statement)
    person = result.unique().scalar_one_or_none()
    if person is not None:
        person.promocode.append(promo_code)
        await session.commit()
        return True
    return False


async def succes_aplication(session: AsyncSession, id_application):
    application = await session.execute(
        select(WithdrawalRequests)
        .filter(WithdrawalRequests.id == id_application)
    )
    application_instance = application.scalar_one_or_none()
    if application_instance is not None:
        application_instance.check_payment = True
        await session.commit()
        return True
    return False


async def update_delete_users_server(session: AsyncSession, server):
    statement = select(Keys).filter(Keys.server == server.id)
    result = await session.execute(statement)
    keys = result.scalars().all()
    if keys is not None:
        for key in keys:
            key.server = None
        await session.commit()
        return True
    else:
        return False


async def update_key_users_server(session: AsyncSession, telegram_id):
    statement = select(Keys).filter(Keys.user_tgid == telegram_id)
    result = await session.execute(statement)
    keys = result.scalars().all()
    if keys is not None:
        for key in keys:
            key.server = None
        await session.commit()
        return True
    else:
        return False

@sinc_time
async def add_time_key(
    session: AsyncSession,
    key_id,
    time_sub,
    id_payment=None
):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        key.subscription += time_sub
        key.id_payment = id_payment
        if not key.notion_oneday:
            key.notion_oneday = False
        if key.trial_period:
            key.trial_period = False
        await session.commit()
        return True
    else:
        return False

@sinc_time
async def new_time_key(session: AsyncSession, key_id, time_sub):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        key.subscription = int(time.time()) + time_sub
        if not key.notion_oneday:
            key.notion_oneday = False
        if key.trial_period:
            key.trial_period = False
        await session.commit()
        return True
    else:
        return False


async def update_switch_key(session: AsyncSession, key_id, action):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        if action:
            key.switch_location += 1
        else:
            if key.switch_location == 0:
                return
            key.switch_location -= 1
        await session.commit()
        return True
    else:
        return False


async def update_switch_key_admin(session: AsyncSession, key_id, count_switch):
    statement = select(Keys).filter(Keys.id == key_id)
    result = await session.execute(statement)
    key = result.scalar_one_or_none()
    if key is not None:
        key.switch_location = count_switch
        await session.commit()
        return True
    else:
        return False


async def update_lang(session: AsyncSession, lang, tgid):
    person = await _get_person(session, tgid)
    if person is not None:
        person.lang = lang
        await session.commit()
        return True
    return False


async def update_auto_pay(session: AsyncSession, new_auto_pay, telegram_id):
    person = await _get_person(session, telegram_id)
    if person is not None:
        person.auto_pay = new_auto_pay
        await session.commit()
        return True
    return False


async def persons_add_group(
    session: AsyncSession,
    list_input,
    name_group=None
):
    statement = select(Persons).filter(Persons.tgid.in_(list_input))
    result = await session.execute(statement)
    persons = result.scalars().all()
    if persons is not None:
        for person in persons:
            person.group = name_group
        await session.commit()
        return len(persons)
    return 0


async def promo_user_use(session: AsyncSession, promo_id, telegram_id):
    promo_statement = select(PromoCode).filter(PromoCode.id == promo_id)
    promo_result = await session.execute(promo_statement)
    promo = promo_result.scalar_one_or_none()

    if promo is not None:
        user_statement = select(Persons).options(
            joinedload(Persons.promocode)
        ).filter(
            Persons.tgid == telegram_id
        )
        user_result = await session.execute(user_statement)
        user = user_result.unique().scalar_one_or_none()

        if user is not None:
            update_statement = update(message_button_association).where(
                message_button_association.c.promocode_id == promo_id,
                message_button_association.c.users_id == user.id
            ).values(use=True)
            await session.execute(update_statement)
            await session.commit()
            return True
    return False


async def block_state_person(session: AsyncSession, telegram_id, block_state):
    person = await _get_person(session, telegram_id)
    if person is not None:
        person.blocked = block_state
        await session.commit()
        return True
    return False


async def status_state_person(
    session: AsyncSession,
    telegram_id,
    status,
    percent
):
    person = await _get_person(session, telegram_id)
    if person is not None:
        person.status = int(status)
        person.referral_percent = int(percent)
        await session.commit()
        return True
    return False


async def new_name_location(session: AsyncSession, location_id, new_name):
    statement = select(Location).filter(Location.id == location_id)
    result = await session.execute(statement)
    location = result.unique().scalar_one_or_none()
    location.name = new_name
    await session.commit()


async def edit_work_location(session: AsyncSession, location_id):
    statement = select(Location).filter(Location.id == location_id)
    result = await session.execute(statement)
    location = result.unique().scalar_one_or_none()
    location.work = not location.work
    work = location.work
    await session.commit()
    return work


async def edit_work_vds(session: AsyncSession, vds_id):
    statement = select(Vds).filter(Vds.id == vds_id)
    result = await session.execute(statement)
    vds = result.unique().scalar_one_or_none()
    vds.work = not vds.work
    work = vds.work
    await session.commit()
    return work


async def new_name_vds(session: AsyncSession, vds_id, new_name):
    statement = select(Vds).filter(Vds.id == vds_id)
    result = await session.execute(statement)
    vds = result.unique().scalar_one_or_none()
    vds.name = new_name
    await session.commit()


async def new_ip_vds(session: AsyncSession, vds_id, new_ip):
    statement = select(Vds).filter(Vds.id == vds_id)
    result = await session.execute(statement)
    vds = result.unique().scalar_one_or_none()
    vds.ip = new_ip
    await session.commit()


async def new_password_vds(session: AsyncSession, vds_id, new_password):
    statement = select(Vds).filter(Vds.id == vds_id)
    result = await session.execute(statement)
    vds = result.unique().scalar_one_or_none()
    vds.vds_password = new_password
    await session.commit()


async def new_limit_vds(session: AsyncSession, vds_id, new_limit):
    statement = select(Vds).filter(Vds.id == vds_id)
    result = await session.execute(statement)
    vds = result.unique().scalar_one_or_none()
    vds.max_space = new_limit
    await session.commit()


async def new_squad_server(
    session: AsyncSession,
    server_id: int,
    squad_uui: str
):
    statement = select(Servers).filter(Servers.id == server_id)
    result = await session.execute(statement)
    server = result.unique().scalar_one_or_none()
    server.remnawave_squad_id = squad_uui
    await session.commit()