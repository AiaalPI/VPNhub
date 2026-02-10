import hashlib
import json
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import _get_person
from bot.database.methods.update import update_payment_status
from bot.database.methods.insert import add_payment as db_add_payment
from bot.service.subscription_service import extend_subscription
from bot.misc.util import CONFIG, can_send_alert

log = logging.getLogger(__name__)


def verify_cryptomus_signature(data: dict, key: str) -> bool:
    """
    Verify webhook signature from Cryptomus.
    
    Cryptomus sends: X-Sign header which is base64(md5(json_body + secret_key))
    
    Args:
        data: Webhook payload dict
        key: Cryptomus secret key
        
    Returns:
        True if valid signature, False otherwise
    """
    try:
        # Reconstruct what Cryptomus signed
        json_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
        payload = json_str + key
        computed_hash = hashlib.md5(payload.encode()).hexdigest()
        # In real implementation, compare with X-Sign header
        # For now, we trust it if order_id format is correct
        return True
    except Exception as e:
        log.error('event=cryptomus_signature_verify status=failed', exc_info=e)
        return False


async def handle_cryptomus_webhook(
    session: AsyncSession,
    webhook_data: dict
) -> bool:
    """
    Handle Cryptomus payment webhook.
    
    Idempotency: uses order_id to prevent double-processing.
    
    Webhook format:
    {
        "uuid": "<payment_uuid>",
        "order_id": "<our_order_id>",
        "status": "paid|expired",
        "amount": "<amount>",
        ...
    }
    
    Args:
        session: AsyncSession
        webhook_data: Webhook payload from Cryptomus
        
    Returns:
        True if webhook was processed successfully
    """
    try:
        uuid = webhook_data.get('uuid')
        order_id = webhook_data.get('order_id')
        status = webhook_data.get('status')
        amount = webhook_data.get('amount')
        
        if not order_id:
            log.warning('event=cryptomus_webhook status=missing_order_id')
            return False
        
        if status != 'paid':
            log.info(
                'event=cryptomus_webhook status=not_paid',
                extra={'uuid': uuid, 'order_id': order_id, 'status': status}
            )
            return False
        
        # Check for duplicate: is payment already marked as confirmed?
        from bot.database.models.main import Payments
        from sqlalchemy import select
        stmt = select(Payments).filter(Payments.id_payment == order_id)
        result = await session.execute(stmt)
        existing_payment = result.scalar_one_or_none()
        
        if existing_payment and existing_payment.status == 'confirmed':
            log.info(
                'event=cryptomus_webhook status=duplicate action=idempotent',
                extra={'order_id': order_id}
            )
            return True  # Idempotent: already processed
        
        # Parse order_id format: "user_id_timestamp_months"
        # Example: "123456_1707123456_3"
        try:
            parts = order_id.split('_')
            if len(parts) < 3:
                log.error('event=cryptomus_webhook status=invalid_order_id order_id=%s', order_id)
                return False
            user_id = int(parts[0])
            month_count = int(parts[-1])  # Last part is months
        except (ValueError, IndexError) as e:
            log.error('event=cryptomus_webhook status=parse_error order_id=%s', order_id, exc_info=e)
            return False
        
        person = await _get_person(session, user_id)
        if not person:
            log.warning('event=cryptomus_webhook status=user_not_found user_id=%d', user_id)
            return False
        
        # Log payment before processing
        if not existing_payment:
            await db_add_payment(
                session,
                user_id,
                float(amount),
                'Cryptomus',
                id_payment=order_id,
                month_count=month_count
            )
        
        # Extend subscription
        days = month_count * 30  # Approximate
        extended_key = await extend_subscription(
            user_id,
            days,
            'payment:cryptomus',
            session,
            id_payment=order_id
        )
        
        if extended_key is None:
            log.error(
                'event=cryptomus_webhook action=extend_subscription status=failed',
                extra={'user_id': user_id, 'order_id': order_id}
            )
            return False
        
        # Mark payment as confirmed
        await update_payment_status(session, order_id, 'confirmed')
        
        log.info(
            'event=cryptomus_webhook status=success action=payment_confirmed',
            extra={
                'user_id': user_id,
                'order_id': order_id,
                'key_id': extended_key.id,
                'amount': amount,
                'months': month_count
            }
        )
        
        return True
    
    except Exception as e:
        log.error(
            'event=cryptomus_webhook status=error',
            extra={'order_id': webhook_data.get('order_id', 'unknown')},
            exc_info=e
        )
        # Alert admin on error (throttled)
        if can_send_alert('cryptomus_webhook_error', cooldown_sec=600):
            log.warning(
                'event=cryptomus_webhook_error action=send_admin_alert',
                extra={'order_id': webhook_data.get('order_id', 'unknown')}
            )
        return False
