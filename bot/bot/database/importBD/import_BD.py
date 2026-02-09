import sqlite3 as sq
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.main import engine
from bot.database.models.main import (
    Persons,
    Payments,
    Keys
)
from bot.misc.util import CONFIG


async def import_all():
    await import_users()
    await import_subscribe()
    await import_payments()


async def import_users():
    try:
        with sq.connect('bot/database/importBD/DatabaseVPN.db') as con:
            cur = con.cursor()
            qyt = ('''
            SELECT * FROM users
            ''')
            output = cur.execute(qyt)
    except Exception as e:
        print('Не удалось получить доступ к базе '
              'данных она должна называться DatabaseVPN.db', e)
    list_users = []
    for user in output:
        user_orm = Persons(
            tgid=int(user[1]),
            username=user[6],
            fullname=user[7],
            referral_user_tgid=user[8],
            referral_balance=user[9],
            lang=user[10],
        )
        list_users.append(user_orm)
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        for user in list_users:
            db.add(user)
            await db.commit()


async def import_subscribe():
    try:
        with sq.connect('bot/database/importBD/DatabaseVPN.db') as con:
            cur = con.cursor()
            qyt = ('''
            SELECT * FROM users
            ''')
            output = cur.execute(qyt)
    except Exception as e:
        print('Не удалось получить доступ к базе '
              'данных она должна называться DatabaseVPN.db', e)
    keys_list = []
    for user in output:
        if int(user[2]) == 0:
            key = Keys(
                user_tgid=user[1],
                subscription=user[4],
                switch_location=CONFIG.free_switch_location,
            )
            keys_list.append(key)
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        for key in keys_list:
            db.add(key)
            await db.commit()


async def import_payments():
    try:
        with sq.connect('bot/database/importBD/DatabaseVPN.db') as con:
            cur = con.cursor()
            qyt = ('''
            SELECT * FROM payments
            ''')
            output = cur.execute(qyt)
    except Exception as e:
        print('Не удалось получить доступ к базе '
              'данных она должна называться DatabaseVPN.db', e)
    list_payments = []
    for server in output:
        payment_orm = Payments(
            user=server[1],
            payment_system=server[2],
            amount=server[3],
            data=datetime.strptime(server[4], '%Y-%m-%d %H:%M:%S.%f'),
        )
        list_payments.append(payment_orm)
    async with AsyncSession(autoflush=False, bind=engine()) as db:
        for payment in list_payments:
            db.add(payment)
        await db.commit()
