import logging
import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.main import Keys
from bot.database.methods.get import _get_person, get_free_server_id, get_key_id
from bot.database.methods.insert import add_key
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)


async def extend_subscription(
    user_id: int,
    days: int,
    reason: str,
    session: AsyncSession,
    id_payment: str | None = None,
    server_id: int | None = None
) -> Keys | None:
    """
    Central function to extend user's subscription.
    
    If user has no active key, creates one. Otherwise extends existing key.
    Logs all extensions with reason for audit trail.
    
    Args:
        user_id: Telegram user ID
        days: Number of days to add
        reason: Reason for extension (e.g., 'payment', 'trial', 'admin_gift')
        session: AsyncSession
        id_payment: Optional payment ID to link to key
        server_id: Optional server ID (used when creating new key)
        
    Returns:
        Updated Key object, or None on failure
    """
    person = await _get_person(session, user_id)
    if person is None:
        log.error('event=extend_subscription reason=user_not_found user_id=%d', user_id)
        return None
    
    now = int(time.time())
    extension_seconds = days * CONFIG.COUNT_SECOND_DAY
    
    # Try to find existing active key
    active_key = None
    for key in person.keys:
        if not key.free_key and key.subscription > now:
            active_key = key
            break
    
    if active_key is None:
        # Create new key if needed
        if server_id is None:
            try:
                server = await get_free_server_id(session, id_loc=None, id_prot=None)
                server_id = server.id if server else None
            except Exception:
                pass
        
        new_key = await add_key(
            session,
            user_id,
            subscription=extension_seconds,
            id_payment=id_payment,
            free_key=False,
            trial_period=False,
            server_id=server_id
        )
        
        log.info(
            'event=subscription_extended action=created_new_key',
            extra={
                'user_id': user_id,
                'key_id': new_key.id,
                'duration_days': days,
                'reason': reason,
                'payment_id': id_payment
            }
        )
        return new_key
    else:
        # Extend existing key
        old_expiry = active_key.subscription
        new_expiry = max(active_key.subscription, now) + extension_seconds
        active_key.subscription = new_expiry
        if id_payment:
            active_key.id_payment = id_payment
        
        await session.commit()
        
        days_added = (new_expiry - old_expiry) // CONFIG.COUNT_SECOND_DAY
        log.info(
            'event=subscription_extended action=extended_existing_key',
            extra={
                'user_id': user_id,
                'key_id': active_key.id,
                'old_expiry': old_expiry,
                'new_expiry': new_expiry,
                'days_added': days_added,
                'reason': reason,
                'payment_id': id_payment
            }
        )
        return active_key
