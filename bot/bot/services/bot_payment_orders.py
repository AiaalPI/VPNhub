"""Payment receipt, entitlement and panel delivery are separate durable steps.

No payment is inferred from a redirect or an elapsed timeout. Provider polling
uses TLS and an exact unpredictable invoice label. Database row locks serialize
retries; panel reconciliation writes absolute values without resetting traffic.
"""
import hashlib
import html
import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import aiohttp
from sqlalchemy import select

from bot.database.models.main import BotPaymentOrder, Donate, Keys, Payments, Persons, ReferralBonus, Servers
from bot.database.methods.get import get_key_id, get_name_location_server
from bot.misc.language import Localization
from bot.misc.tariffs import get_paid_data_limit_gb
from bot.misc.util import CONFIG
from bot.misc.VPN.ServerManager import ServerManager
from bot.services.panel_healing_service import restore_panel_client_access

log = logging.getLogger(__name__)
_ = Localization.text


def kopecks(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0 or amount * 100 != (amount * 100).to_integral_value():
        raise ValueError('Invalid payment amount')
    return int(amount * 100)


def matches_receipt(order, operation):
    """History reports net receipts. AC form commission is 3% (YooMoney docs).

    Require the invoiced net proceeds, not the old arbitrary 4% discount. A
    native signed webhook can verify gross amounts; this path requires no new
    notification secret and works with the installed wallet API token.
    """
    if not isinstance(operation, dict) or operation.get('label') != order.id:
        return False
    if operation.get('status') != 'success' or operation.get('direction') != 'in':
        return False
    if operation.get('codepro') in (True, 'true') or operation.get('unaccepted') in (True, 'true'):
        return False
    operation_id = operation.get('operation_id')
    if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 128:
        return False
    try:
        minimum = int((Decimal(order.amount_kopecks) * Decimal('0.97')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        return kopecks(operation.get('amount')) >= minimum
    except (InvalidOperation, ValueError, TypeError):
        return False


async def create_order(payment, order_id=None):
    codes = {value: key for key, value in CONFIG.type_payment.items()}
    code = codes[payment.TYPE_PAYMENT]
    if code in (0, 1) and int(payment.month_count or 0) not in (1, 3, 6, 12):
        raise ValueError('Invalid subscription duration')
    order = BotPaymentOrder(
        id=order_id or 'vb2_' + uuid.uuid4().hex,
        user_tgid=payment.user_id, type_pay=code,
        requested_key_id=int(payment.KEY_ID or 0) or None,
        months=int(payment.month_count or 1), amount_kopecks=kopecks(payment.price),
        protocol=int(payment.ID_PROT or 0), location=int(payment.ID_LOC or 0),
        created_at=int(time.time()), next_attempt=int(time.time()),
    )
    payment.session.add(order)
    await payment.session.commit()
    return order


async def payment_helper(session, bot, order):
    # Lazy import avoids the provider/helper import cycle.
    from bot.webhooks.util import get_message
    from bot.misc.Payment.payment_systems import PaymentSystem
    return PaymentSystem(session, await get_message(bot, order.user_tgid), order.user_tgid,
                         CONFIG.type_payment[order.type_pay], order.requested_key_id,
                         order.protocol, order.location, order.amount_kopecks / 100, order.months)


async def bind_receipt(session, order_id, operation_id):
    """Persist authenticated receipt before potentially failing server selection."""
    order = await session.scalar(select(BotPaymentOrder).where(BotPaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if not order or not operation_id or len(operation_id) > 128:
        raise ValueError('Invalid payment receipt')
    if order.operation_id and order.operation_id != operation_id:
        raise ValueError('Order already has a receipt')
    order.operation_id = operation_id
    order.next_attempt = int(time.time())
    await session.commit()


async def credit_order(session, bot, order_id, operation_id, provider='YooMoney'):
    """Caller must authenticate the provider receipt or be an authorized admin.

    All monetary/entitlement mutations commit together. No network delivery or
    committing legacy database helpers are allowed inside this transaction.
    """
    order = await session.scalar(select(BotPaymentOrder).where(BotPaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise ValueError('Unknown payment order')
    if order.paid_at:
        if order.operation_id != operation_id:
            raise ValueError('Order already credited by another operation')
        await session.commit()
        return
    if not operation_id or len(operation_id) > 128:
        raise ValueError('Invalid operation identifier')
    existing = await session.scalar(select(Payments.id).where(Payments.id_payment == operation_id))
    if existing:
        raise ValueError('Operation already credited')
    person = await session.scalar(select(Persons).where(Persons.tgid == order.user_tgid).with_for_update().execution_options(populate_existing=True))
    if person is None or person.blocked:
        raise ValueError('Account unavailable')
    helper = await payment_helper(session, bot, order)
    now = int(time.time())
    key = None
    if order.type_pay == 0:
        server = await helper._resolve_server_for_new_key()
        if server is None:
            raise RuntimeError('No available server')
        if int(server.type_vpn) == CONFIG.TypeVpn.MARZBAN.value:
            candidate = await helper._get_user_best_marzban_key(person.tgid)
            if candidate:
                key = await session.scalar(select(Keys).where(Keys.id == candidate.id).with_for_update().execution_options(populate_existing=True))
        if key is None:
            key = Keys(user_tgid=person.tgid, subscription=now, server=server.id,
                       paid_quota_gb=0, switch_location=CONFIG.free_switch_location,
                       free_key=False, trial_period=False)
            session.add(key)
            await session.flush()
    elif order.type_pay in (1, 3):
        key = await session.scalar(select(Keys).where(Keys.id == order.requested_key_id,
            Keys.user_tgid == order.user_tgid).with_for_update().execution_options(populate_existing=True))
        if key is None or key.free_key:
            raise ValueError('Owned paid key required')
    if order.type_pay in (0, 1):
        key.subscription = max(int(key.subscription or 0), now) + order.months * CONFIG.COUNT_SECOND_MOTH
        key.id_payment = operation_id
        if key.paid_quota_gb is None:
            # Capture legacy allowance once; do not assume a different tariff.
            server = await session.get(Servers, key.server)
            manager = ServerManager(server)
            await manager.login()
            identity = key.wg_public_key if server.type_vpn == CONFIG.TypeVpn.WIREGUARD.value else key.user_tgid
            client = await manager.client.get_client(f'{identity}.{key.id}.{manager.client.POST_FIX}')
            limit_bytes = client.get('data_limit', 0) if isinstance(client, dict) else getattr(client, 'totalGB', 0)
            key.paid_quota_gb = (int(limit_bytes or 0) + 1073741823) // 1073741824
        key.paid_quota_gb += get_paid_data_limit_gb(order.months)
        key.trial_period = False
        key.notion_oneday = key.notified_1day = key.notified_3days = key.notified_expired = False
        order.key_id = key.id
    elif order.type_pay == 2:
        session.add(Donate(username=person.username, price=order.amount_kopecks / 100))
    elif order.type_pay == 3:
        key.switch_location = int(key.switch_location or 0) + 1
    else:
        raise ValueError('Unknown purchase type')
    # Preserve the existing three-day referral benefit, exactly once per order.
    if person.referral_user_tgid and person.referral_user_tgid != person.tgid:
        bonus = await session.scalar(select(Keys).where(Keys.user_tgid == person.referral_user_tgid,
            Keys.free_key.is_(False)).order_by(Keys.subscription.desc()).limit(1).with_for_update().execution_options(populate_existing=True))
        if bonus:
            bonus.subscription = max(int(bonus.subscription or 0), now) + 3 * 86400
            bonus.notified_1day = bonus.notified_3days = bonus.notified_expired = bonus.notion_oneday = False
            order.bonus_key_id = bonus.id
            session.add(ReferralBonus(referrer_id=person.referral_user_tgid, referee_id=person.tgid,
                                      bonus_days=3, payment_id=operation_id))
    session.add(Payments(user=person.id, id_payment=operation_id, month_count=order.months,
                         payment_system=provider, amount=order.amount_kopecks / 100,
                         data=datetime.now(timezone.utc).replace(tzinfo=None), status='paid'))
    order.paid_at = now
    order.operation_id = operation_id
    order.next_attempt = now
    await session.commit()


async def provision_key(session, key):
    person = await session.scalar(select(Persons).where(Persons.tgid == key.user_tgid))
    if person is None or person.blocked or key.subscription <= int(time.time()):
        raise ValueError('Subscription unavailable')
    manager = ServerManager(key.server_table)
    await manager.login()
    location = await get_name_location_server(session, key.server)
    wireguard = key.server_table.type_vpn == CONFIG.TypeVpn.WIREGUARD.value
    identity = key.wg_public_key if wireguard else key.user_tgid
    config = await manager.get_key(identity, location, key.id,
                                   subscription_timestamp=key.subscription, limit_gb=key.paid_quota_gb)
    if not config:
        raise RuntimeError('Panel returned no configuration')
    if wireguard:
        key.wg_public_key = config.public_key
    person.banned = False
    clients = await manager.get_all_user()
    if clients is not None:
        key.server_table.actual_space = len(clients)
    return config


async def fulfill_order(session, bot, order_id):
    # Lock held through panel reconciliation so concurrent deliveries cannot
    # overwrite a newer entitlement. Every retry reads the current key expiry.
    order = await session.scalar(select(BotPaymentOrder).where(BotPaymentOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if not order or not order.paid_at or order.completed:
        await session.commit()
        return
    helper = await payment_helper(session, bot, order)
    person = await session.scalar(select(Persons).where(Persons.tgid == order.user_tgid))
    if not person or person.blocked:
        raise ValueError('Account unavailable')
    config = None
    key = None
    if order.key_id:
        await session.scalar(select(Keys).where(Keys.id == order.key_id).with_for_update().execution_options(populate_existing=True))
        key = await get_key_id(session, order.key_id)
        if not order.fulfilled or not order.user_notified:
            config = await provision_key(session, key)
    order.fulfilled = True
    await session.commit()
    # Telegram delivery is at-least-once: a crash after send may repeat a message,
    # but never credits another payment, duration, key or referral benefit.
    if not order.user_notified:
        if key:
            await helper.post_key(person.lang, key, config)
            await helper.message.answer(_('payment_key_activated_user', person.lang).format(
                date=helper._format_expire_date(key.subscription), server=helper._resolve_server_name(key)))
        else:
            text_key = 'donate_successful' if order.type_pay == 2 else 'payment_success_switch'
            await helper.message.answer(_(text_key, person.lang))
        order.user_notified = True
        await session.commit()
    if not order.admin_notified:
        await helper._notify_admin_payment(person, order.amount_kopecks / 100)
        order.admin_notified = True
        await session.commit()
    if order.bonus_key_id and not order.bonus_synced:
        bonus = await session.get(Keys, order.bonus_key_id)
        bonus_owner = await session.scalar(select(Persons).where(Persons.tgid == bonus.user_tgid)) if bonus else None
        if bonus and bonus_owner and not bonus_owner.blocked and bonus.subscription > int(time.time()):
            result = await restore_panel_client_access(session, bonus, reason='payment_referral')
            if result.status not in ('restored', 'skipped'):
                raise RuntimeError('Referral panel update pending')
            await bot.send_message(bonus_owner.tgid, _('referral_friend_paid_bonus', bonus_owner.lang).format(
                name=html.escape(person.fullname or person.username or str(person.tgid)), days=3))
        order.bonus_synced = True
    order.completed = True
    order.last_error = None
    await session.commit()


async def find_receipt(http, order):
    cursor = None
    for _page in range(10):
        data = {'label': order.id, 'records': 100, 'type': 'deposition'}
        if cursor is not None:
            data['start_record'] = cursor
        async with http.post('https://yoomoney.ru/api/operation-history', data=data) as response:
            response.raise_for_status()
            body = await response.json()
        if not isinstance(body, dict) or body.get('error') or not isinstance(body.get('operations'), list):
            raise RuntimeError('Invalid provider history response')
        for operation in body['operations']:
            if matches_receipt(order, operation):
                return operation['operation_id']
        cursor = body.get('next_record')
        if cursor is None:
            return None
    raise RuntimeError('Provider history pagination limit')


async def process_payment_orders(bot, sessionmaker):
    """Restart-safe bounded queue. Old unpaid invoices are checked hourly."""
    now = int(time.time())
    async with sessionmaker() as session:
        ids = list((await session.scalars(select(BotPaymentOrder.id).where(
            BotPaymentOrder.completed.is_(False), BotPaymentOrder.next_attempt <= now)
            .order_by(BotPaymentOrder.next_attempt).limit(30))).all())
    if not ids:
        return
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
        headers={'Authorization': 'Bearer ' + CONFIG.yoomoney_token}) as http:
        for order_id in ids:
            async with sessionmaker() as session:
                try:
                    order = await session.get(BotPaymentOrder, order_id)
                    if not order.paid_at:
                        operation = order.operation_id or await find_receipt(http, order)
                        if operation:
                            await bind_receipt(session, order_id, operation)
                            await credit_order(session, bot, order_id, operation)
                        else:
                            order.next_attempt = int(time.time()) + (30 if now - order.created_at < 3600 else 3600)
                            await session.commit()
                            continue
                    await fulfill_order(session, bot, order_id)
                except Exception as exc:
                    await session.rollback()
                    order = await session.get(BotPaymentOrder, order_id)
                    order.attempts += 1
                    order.next_attempt = int(time.time()) + min(900, 15 * 2 ** min(order.attempts, 6))
                    order.last_error = type(exc).__name__
                    await session.commit()
                    # Never log response bodies, bearer tokens or VPN links.
                    log.warning('event=payment_order.retry order=%s error_type=%s', order_id, type(exc).__name__)


async def legacy_confirmed_payment(payment, amount, provider, operation_id):
    """Route explicit legacy YooMoney admin/bridge receipts into the same outbox."""
    if not operation_id or kopecks(amount) != kopecks(payment.price):
        raise ValueError('A stable identifier and matching payment amount are required')
    order_id = 'manual_' + hashlib.sha256(operation_id.encode()).hexdigest()[:48]
    order = await payment.session.get(BotPaymentOrder, order_id)
    if order is None:
        # Already processed by the pre-migration implementation: do not credit again.
        if await payment.session.scalar(select(Payments.id).where(Payments.id_payment == operation_id)):
            return
        order = await create_order(payment, order_id)
    order_id = order.id
    await bind_receipt(payment.session, order_id, operation_id)
    try:
        await credit_order(payment.session, payment.message.bot, order_id, operation_id, provider)
        await fulfill_order(payment.session, payment.message.bot, order_id)
    except Exception:
        await payment.session.rollback()
        log.warning('event=payment_order.delivery_pending order=%s', order_id)
