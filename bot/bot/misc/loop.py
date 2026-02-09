import logging
import time

from aiogram import Bot
from aiogram.types import FSInputFile
from nats.js import JetStreamContext
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from bot.database.methods.delete import delete_key_in_user
from bot.database.methods.insert import add_payment
from bot.database.methods.get import (
    get_all_subscription,
    get_server_id,
    get_payment
)
from bot.database.methods.update import (
    person_banned_true,
    key_one_day_true,
    server_space_update,
    add_time_key
)
from bot.keyboards.inline.user_inline import mailing_button_message
from bot.misc.Payment.KassaSmart import KassaSmart
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.language import Localization
from bot.misc.remove_key_servise.publisher import remove_key_server
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)

_ = Localization.text

COUNT_SECOND_DAY = 86400

month_count_amount = {
    12: CONFIG.month_cost[3],
    6: CONFIG.month_cost[2],
    3: CONFIG.month_cost[1],
    1: CONFIG.month_cost[0],
}


async def loop(
    bot: Bot,
    session_pool: async_sessionmaker,
    js: JetStreamContext,
    remove_key_subject: str
):
    try:
        async with session_pool() as session:
            all_persons = await get_all_subscription(session)
            for person in all_persons:
                await check_date(person, bot, session, js, remove_key_subject)
    except Exception as e:
        log.error(e)


async def check_date(
    person,
    bot: Bot,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str
):
    try:
        for key in person.keys:
            if key.free_key:
                continue
            if key.subscription <= int(time.time()):
                await delete_key(session, js, remove_key_subject, key)
                person.keys.remove(key)
                if len(person.keys) == 0:
                    await person_banned_true(session, person.tgid)
                try:
                    await bot.send_photo(
                        chat_id=person.tgid,
                        photo=FSInputFile('bot/img/ended_subscribe.jpg'),
                        caption=_('ended_sub_message', person.lang),
                        reply_markup = await mailing_button_message(
                            person.lang, CONFIG.type_buttons_mailing[0]
                        )
                    )
                except Exception:
                    log.info(f'User {person.tgid} blocked bot')
                    continue
            elif (key.subscription <= int(time.time()) + COUNT_SECOND_DAY
                  and not key.notion_oneday):
                await key_one_day_true(session, key_id=key.id)
                try:
                    await bot.send_message(
                        person.tgid,
                        _('alert_to_renew_sub', person.lang),
                        disable_web_page_preview=True,
                        reply_markup=await mailing_button_message(
                            person.lang, CONFIG.type_buttons_mailing[0]
                        )
                    )
                except Exception:
                    log.info(f'User {person.tgid} blocked bot')
                    continue
    except Exception as e:
        log.error(
            "Error in the user date verification cycle: %s", exc_info=e
        )
        return


async def delete_key(
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    key
):
    await delete_key_in_user(session, key.id)
    if key.server is not None:
        server = await get_server_id(session, key.server)
        try:
            await remove_key_server(
                js,
                remove_key_subject,
                key.user_tgid,
                key.id,
                server.id,
                key.wg_public_key
            )
            server_manager = ServerManager(server)
            await server_manager.login()
            all_client = await server_manager.get_all_user()
        except Exception as e:
            log.error("Failed to connect to the server", exc_info=e)
            raise e
        space = len(all_client)
        if not await server_space_update(session, server.id, space):
            raise


async def auto_pay_yookassa(
    session: AsyncSession,
    person,
    key,
    bot: Bot
) -> bool:
    if key.id_payment is None:
        return False
    payment = await get_payment(session, key.id_payment)
    if payment.month_count is None:
        return False
    price = int(month_count_amount.get(payment.month_count))
    payment_system = await KassaSmart.auto_payment(
        config=CONFIG,
        lang_user=person.lang,
        payment_id=payment.id_payment,
        price=price
    )
    if payment_system is None:
        return False
    log.info(
        f'user ID: {person.tgid}'
        f' success auto payment {price} RUB Payment - YooKassaSmart'
    )
    await add_payment(
        session,
        person.tgid,
        price,
        'KassaSmart',
        id_payment=payment.id_payment,
        month_count=payment.month_count
    )
    await add_time_key(
        session,
        key.id,
        payment.month_count * CONFIG.COUNT_SECOND_MOTH,
        id_payment=payment.id_payment
    )
    try:
        await bot.send_message(
            chat_id=person.tgid,
            text=_('loop_autopay_text', person.lang).format(
                month_count=payment.month_count
            )
        )
    except Exception:
        log.info(f'User {person.tgid} blocked bot')
    return True
