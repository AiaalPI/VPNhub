import logging
import time
from time import perf_counter

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
    add_time_key
)
from bot.keyboards.inline.user_inline import mailing_button_message
from bot.misc.Payment.KassaSmart import KassaSmart
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
    start = perf_counter()
    counters = {
        'keys_expired_processed': 0,
        'keys_deleted': 0,
        'trials_expired_processed': 0,
    }
    log.debug('job.loop.start')
    try:
        async with session_pool() as session:
            all_persons = await get_all_subscription(session)
            for person in all_persons:
                # Check regular subscription expiry
                await check_date(person, bot, session, js, remove_key_subject, counters)
                # Check trial expiry
                await check_trial_expiry(person, bot, session, counters)
    except Exception as e:
        log.error('job.loop.error', exc_info=e)
    finally:
        duration = perf_counter() - start
        log.debug(
            'job.loop.done',
            extra={
                'duration_s': round(duration, 3),
                'keys_expired_processed': counters['keys_expired_processed'],
                'keys_deleted': counters['keys_deleted'],
                'trials_expired_processed': counters['trials_expired_processed']
            }
        )


async def check_date(
    person,
    bot: Bot,
    session: AsyncSession,
    js: JetStreamContext,
    remove_key_subject: str,
    counters: dict | None = None
):
    try:
        for key in person.keys:
            if key.free_key:
                continue
            if key.subscription <= int(time.time()):
                # count attempted expired key processing
                if counters is not None:
                    counters['keys_expired_processed'] += 1

                # structured log before deletion attempt
                days_left = max(
                    0,
                    (key.subscription - int(time.time())) // COUNT_SECOND_DAY
                )
                server_id = getattr(key, 'server', None)
                log.info('event=subscription_expiry action=delete_attempt', extra={
                    'user_id': person.tgid,
                    'key_id': key.id,
                    'server_id': server_id,
                    'days_left': int(days_left)
                })

                try:
                    await delete_key(session, js, remove_key_subject, key)
                    # successful delete
                    if counters is not None:
                        counters['keys_deleted'] += 1
                    log.info('event=subscription_expiry action=deleted', extra={
                        'user_id': person.tgid,
                        'key_id': key.id,
                        'server_id': server_id,
                        'days_left': int(days_left)
                    })
                except Exception as e:
                    log.error('event=subscription_expiry action=delete_failed key_id=%s', key.id, exc_info=e)
                    raise
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
    """Delete key from DB and publish NATS remove-key event.
    
    Server space recalculation is handled by server_control_manager in its
    periodic check, not here, to avoid heavy server calls in the tight loop.
    """
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
        except Exception as e:
            log.error("Failed to publish remove-key event to NATS", exc_info=e)
            raise e


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

async def check_trial_expiry(
    person,
    bot: Bot,
    session: AsyncSession,
    counters: dict | None = None
):
    """
    Check if user's trial period has expired.
    
    If trial is expired:
    - Mark trial_period = False on person
    - Mark trial keys as work = False OR delete them
    - Notify user
    """
    from datetime import datetime
    
    try:
        if not person.trial_period:
            return
        
        if person.trial_expires_at is None:
            # Trial flag set but no expiry time; set it now
            return
        
        now = datetime.now()
        if person.trial_expires_at > now:
            # Trial still active
            return
        
        # Trial expired
        if counters is not None:
            counters['trials_expired_processed'] += 1
        
        log.info(
            'event=trial_expiry action=expired',
            extra={
                'user_id': person.tgid,
                'trial_expires_at': person.trial_expires_at.isoformat()
            }
        )
        
        # Mark trial as expired
        person.trial_period = False
        person.trial_expires_at = None
        await session.commit()
        
        # Delete trial keys or mark them as expired
        trial_keys_count = 0
        for key in person.keys:
            if key.trial_period:
                trial_keys_count += 1
                # Set expiry to now (will be picked up by check_date next time)
                key.subscription = int(time.time())
        
        if trial_keys_count > 0:
            await session.commit()
        
        # Notify user
        try:
            await bot.send_message(
                person.tgid,
                _('trial_expired_message', person.lang),
                reply_markup=await mailing_button_message(
                    person.lang, CONFIG.type_buttons_mailing[0]
                )
            )
        except Exception:
            log.info(f'User {person.tgid} blocked bot (trial expiry notification)')
    
    except Exception as e:
        log.error(
            'event=trial_expiry action=check_failed user_id=%d',
            person.tgid,
            exc_info=e
        )
