import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.methods.get import _get_person
from bot.database.methods.insert import add_payment as db_add_payment
from bot.database.methods.update import update_payment_status
from bot.database.models.main import Payments
from bot.misc.util import can_send_alert
from bot.services.subscription_mutation_service import extend_subscription

log = logging.getLogger(__name__)


async def handle_cryptomus_webhook(
    session: AsyncSession,
    webhook_data: dict
) -> bool:
    """
    Handle Cryptomus webhook payload in an idempotent way.

    This helper is currently exercised in tests and runbooks, but it is not
    mounted as a live FastAPI route in the production webhook app.
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

        stmt = select(Payments).filter(Payments.id_payment == order_id)
        result = await session.execute(stmt)
        existing_payment = result.scalar_one_or_none()

        if existing_payment and existing_payment.status == 'confirmed':
            log.info(
                'event=cryptomus_webhook status=duplicate action=idempotent',
                extra={'order_id': order_id}
            )
            return True

        try:
            parts = order_id.split('_')
            if len(parts) < 3:
                log.error(
                    'event=cryptomus_webhook status=invalid_order_id order_id=%s',
                    order_id
                )
                return False
            user_id = int(parts[0])
            month_count = int(parts[-1])
        except (ValueError, IndexError) as exc:
            log.error(
                'event=cryptomus_webhook status=parse_error order_id=%s',
                order_id,
                exc_info=exc
            )
            return False

        person = await _get_person(session, user_id)
        if not person:
            log.warning(
                'event=cryptomus_webhook status=user_not_found user_id=%d',
                user_id
            )
            return False

        if not existing_payment:
            await db_add_payment(
                session,
                user_id,
                float(amount),
                'Cryptomus',
                id_payment=order_id,
                month_count=month_count
            )

        days = month_count * 30
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

        await update_payment_status(session, order_id, 'confirmed')

        log.info(
            'event=cryptomus_webhook status=success action=payment_confirmed',
            extra={
                'user_id': user_id,
                'order_id': order_id,
                'key_id': extended_key.id,
                'amount': amount,
                'months': month_count,
            }
        )
        return True

    except Exception as exc:
        log.error(
            'event=cryptomus_webhook status=error',
            extra={'order_id': webhook_data.get('order_id', 'unknown')},
            exc_info=exc
        )
        if can_send_alert('cryptomus_webhook_error', cooldown_sec=600):
            log.warning(
                'event=cryptomus_webhook_error action=send_admin_alert',
                extra={'order_id': webhook_data.get('order_id', 'unknown')}
            )
        return False
