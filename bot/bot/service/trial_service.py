import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Persons, Keys
from bot.database.methods.get import _get_person, get_free_server_id
from bot.database.methods.insert import add_key
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)


async def is_trial_eligible(user_id: int, session: AsyncSession) -> bool:
    """
    Check if user is eligible for trial period.
    
    Rules:
    - User must not already have trial_period = True
    - User must not be banned
    - User must not have any active paid subscriptions
    
    Args:
        user_id: Telegram user ID
        session: AsyncSession
        
    Returns:
        True if user can activate trial, False otherwise
    """
    person = await _get_person(session, user_id)
    if person is None:
        log.warning('event=trial_eligibility user_not_found user_id=%d', user_id)
        return False
    
    # Already has trial
    if person.trial_period:
        log.info('event=trial_eligibility reason=already_has_trial user_id=%d', user_id)
        return False
    
    # User is banned
    if person.banned:
        log.info('event=trial_eligibility reason=user_banned user_id=%d', user_id)
        return False
    
    # Check if has any active paid keys (non-trial, non-free)
    current_time = int(time.time())
    for key in person.keys:
        if not key.trial_period and not key.free_key and key.subscription > current_time:
            log.info(
                'event=trial_eligibility reason=has_active_paid_key user_id=%d key_id=%d',
                user_id, key.id
            )
            return False
    
    return True


async def activate_trial(user_id: int, session: AsyncSession) -> Keys | None:
    """
    Activate trial subscription for a user.
    
    Sets:
    - Persons.trial_period = True
    - Persons.trial_activated_at = now
    - Persons.trial_expires_at = now + TRIAL_PERIOD seconds
    - Creates a trial Key with trial_period = True
    
    Args:
        user_id: Telegram user ID
        session: AsyncSession
        
    Returns:
        Created trial Key, or None on failure
    """
    if not await is_trial_eligible(user_id, session):
        log.warning('event=trial_activation reason=not_eligible user_id=%d', user_id)
        return None
    
    person = await _get_person(session, user_id)
    if person is None:
        return None
    
    now = datetime.now()
    trial_duration_s = CONFIG.trial_period
    
    # Mark person as in trial
    person.trial_period = True
    person.trial_activated_at = now
    person.trial_expires_at = now + timedelta(seconds=trial_duration_s)
    person.banned = False  # Unban for trial
    
    # Get free server if available
    try:
        server = await get_free_server_id(session, id_loc=None, id_prot=None)
        server_id = server.id if server else None
    except Exception:
        server_id = None
    
    # Create trial key
    try:
        trial_key = await add_key(
            session,
            user_id,
            subscription=trial_duration_s,
            free_key=False,
            trial_period=True,
            server_id=server_id
        )
        
        log.info(
            'event=trial_activation status=success',
            extra={
                'user_id': user_id,
                'key_id': trial_key.id,
                'trial_expires_at': person.trial_expires_at.isoformat()
            }
        )
        return trial_key
    
    except Exception as e:
        log.error(
            'event=trial_activation status=failed',
            extra={'user_id': user_id},
            exc_info=e
        )
        return None
