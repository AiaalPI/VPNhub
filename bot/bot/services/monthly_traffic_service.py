"""Calendar-month allowances over monotonic panel counters.

Persist each new baseline BEFORE applying its absolute panel ceiling. A timeout
or process crash can retry the same ceiling without giving another allowance.
No panel reset endpoint or automatic-expiry-renewal flag is used.
"""
import calendar
import logging
import time
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import select

from bot.database.models.main import Keys, Persons, Servers, TrafficPolicy
from bot.misc.tariffs import get_paid_data_limit_gb
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.VPN.Xui.Vless import Vless
from bot.portal.models import WebAccount, WebSubscription
from bot.services.subscription_usage_service import SubscriptionUsage, usage_from_global_clients

log = logging.getLogger(__name__)
GIB = 1073741824
BILLING_ZONE = ZoneInfo('Asia/Yakutsk')


def next_month_boundary(anchor: int, now: int) -> int:
    """Jan 31 → Feb 28/29 → Mar 31, preserving the activation's local time."""
    origin = datetime.fromtimestamp(anchor, BILLING_ZONE)
    current = datetime.fromtimestamp(max(now, anchor), BILLING_ZONE)
    offset = (current.year - origin.year) * 12 + current.month - origin.month
    while True:
        year, month0 = divmod(origin.year * 12 + origin.month - 1 + offset, 12)
        month = month0 + 1
        candidate = origin.replace(year=year, month=month,
                                   day=min(origin.day, calendar.monthrange(year, month)[1]))
        if candidate.timestamp() > max(now, anchor):
            return int(candidate.timestamp())
        offset += 1


async def configure_policy(session, *, key=None, sub=None, months: int, now=None, anchor=None, restart=False):
    """Part of the purchase transaction; does not commit or contact the panel."""
    if (key is None) == (sub is None) or months not in (1, 3, 6, 12):
        raise ValueError('Invalid monthly policy target')
    now = int(time.time()) if now is None else int(now)
    server_id = key.server if key is not None else sub.server_id
    server = await session.get(Servers, server_id)
    # This reconciler uses the global XUI VLESS API; never pretend other panels
    # enforce a policy they do not implement.
    from bot.misc.util import CONFIG
    if server is None or int(server.type_vpn) != CONFIG.TypeVpn.VLESS.value:
        raise ValueError('Monthly traffic requires an XUI VLESS server')
    clause = TrafficPolicy.key_id == key.id if key is not None else TrafficPolicy.web_subscription_id == sub.id
    policy = await session.scalar(select(TrafficPolicy).where(clause).with_for_update())
    email = f'{key.user_tgid}.{key.id}.vl' if key is not None else 'web.' + sub.id
    if policy is None:
        start = int(anchor or now)
        policy = TrafficPolicy(server_id=server_id, email=email,
            key_id=key.id if key is not None else None,
            web_subscription_id=sub.id if sub is not None else None,
            anchor_at=start, next_reset_at=next_month_boundary(start, now),
            months=months, quota_gb=get_paid_data_limit_gb(months))
        session.add(policy)
    else:
        if policy.server_id != server_id or policy.email != email:
            raise ValueError('Monthly traffic identity moved; explicit migration required')
        # Active renewals keep this month's used bytes. A genuinely expired
        # subscription starts a new billing cycle on its paid reactivation.
        if restart:
            policy.anchor_at = now
            policy.next_reset_at = next_month_boundary(now, now)
            policy.baseline_upload = policy.baseline_download = None
            policy.panel_limit_bytes = None
        policy.months = months
        policy.quota_gb = get_paid_data_limit_gb(months)
        policy.applied_at = None
        if policy.baseline_upload is not None:
            policy.panel_limit_bytes = (policy.baseline_upload + policy.baseline_download + policy.quota_gb * GIB) if policy.quota_gb else 0
    if key is not None:
        key.paid_quota_gb = policy.quota_gb
    else:
        sub.quota_bytes = policy.quota_gb * GIB
    return policy


async def _target(session, policy, now):
    if policy.key_id is not None:
        target = await session.get(Keys, policy.key_id, populate_existing=True)
        person = await session.scalar(select(Persons).where(Persons.tgid == target.user_tgid)) if target else None
        if not target or not person or person.blocked or target.free_key or target.trial_period:
            return None
        if target.server != policy.server_id or f'{target.user_tgid}.{target.id}.vl' != policy.email:
            raise ValueError('Monthly traffic key identity mismatch')
        expiry = target.subscription
    else:
        target = await session.get(WebSubscription, policy.web_subscription_id, populate_existing=True)
        account = await session.get(WebAccount, target.account_id) if target else None
        if not target or not account or account.disabled:
            return None
        if target.server_id != policy.server_id or 'web.' + target.id != policy.email:
            raise ValueError('Monthly traffic web identity mismatch')
        expiry = target.expires_at
    return (target, int(expiry)) if expiry and expiry > now else None


def _row(response, email):
    # Validates exact nonnegative counters and one global identity.
    usage_from_global_clients(response, email)
    return next(row for row in response['obj'] if row['email'] == email)


async def reconcile_policy(session, policy_id: int, *, now=None):
    now = int(time.time()) if now is None else int(now)
    policy = await session.scalar(select(TrafficPolicy).where(TrafficPolicy.id == policy_id)
                                  .with_for_update().execution_options(populate_existing=True))
    if policy is None or not await _target(session, policy, now):
        await session.commit()
        return False
    server = await session.get(Servers, policy.server_id)
    if not server or not server.work:
        await session.commit()
        return False
    manager = ServerManager(server, timeout=8)
    if not isinstance(manager.client, Vless):
        raise ValueError('Unsupported monthly traffic panel')
    xui = manager.client.xui
    try:
        await manager.login()
        row = _row(await xui.request(method='GET', endpoint='/panel/api/clients/list'), policy.email)
        usage = usage_from_global_clients({'success': True, 'obj': [row]}, policy.email)
        if policy.baseline_upload is None or now >= policy.next_reset_at:
            policy.baseline_upload, policy.baseline_download = usage.upload, usage.download
            policy.next_reset_at = next_month_boundary(policy.anchor_at, now)
            policy.panel_limit_bytes = (usage.upload + usage.download + policy.quota_gb * GIB) if policy.quota_gb else 0
            policy.applied_at = None
        # A quota change is also an absolute target. Commit it before the network
        # write, then reacquire the row lock to serialize stale jobs/renewals.
        await session.commit()
        policy = await session.scalar(select(TrafficPolicy).where(TrafficPolicy.id == policy_id)
                                      .with_for_update().execution_options(populate_existing=True))
        target = await _target(session, policy, now)
        if not target:
            await session.commit()
            return False
        row = _row(await xui.request(method='GET', endpoint='/panel/api/clients/list'), policy.email)
        usage = usage_from_global_clients({'success': True, 'obj': [row]}, policy.email)
        if usage.upload < policy.baseline_upload or usage.download < policy.baseline_download:
            raise ValueError('Panel counters were reset outside monthly accounting')
        if not row.get('uuid'):
            raise ValueError('Missing monthly client identity')
        if policy.web_subscription_id and row['uuid'] != target[0].client_uuid:
            raise ValueError('Monthly web UUID mismatch')
        desired = int(policy.panel_limit_bytes)
        quota_disabled = usage.total > 0 and usage.upload + usage.download >= usage.total
        restore = quota_disabled and (desired == 0 or usage.upload + usage.download < desired)
        payload = {k: v for k, v in row.items() if k not in ('id', 'uuid', 'traffic', 'inboundIds', 'createdAt', 'updatedAt')}
        payload['id'] = row['uuid']
        payload['totalGB'] = desired
        payload['reset'] = 0  # This flag auto-renews expiry in XUI 3.3.1.
        payload['expiryTime'] = max(int(row.get('expiryTime') or 0), target[1] * 1000)
        payload['enable'] = bool(row.get('enable')) or restore
        if (row['totalGB'] != desired or row.get('reset', 0) != 0
                or row.get('expiryTime') != payload['expiryTime'] or row.get('enable') != payload['enable']):
            result = await xui.request(method='POST', endpoint='/panel/api/clients/update/' + quote(policy.email, safe=''), json=payload)
            if not isinstance(result, dict) or not result.get('success'):
                raise ValueError('Panel rejected monthly allowance')
            verified = _row(await xui.request(method='GET', endpoint='/panel/api/clients/list'), policy.email)
            if any(verified.get(k) != payload[k] for k in ('totalGB', 'expiryTime', 'enable', 'reset')) or verified['uuid'] != row['uuid']:
                raise ValueError('Monthly allowance verification failed')
        policy.applied_at = now
        await session.commit()
        return True
    except Exception:
        await session.rollback()
        raise
    finally:
        await xui.close()


async def sync_key_policy(session, key_id, *, required=True):
    policy_id = await session.scalar(select(TrafficPolicy.id).where(TrafficPolicy.key_id == key_id))
    if policy_id:
        try:
            await reconcile_policy(session, policy_id)
        except Exception as exc:
            if required:
                raise
            # Connection exports remain available when accounting needs repair.
            # Never reset counters or fabricate an unlimited allowance here.
            log.warning('event=subscription_policy_sync_unavailable reason=%s', type(exc).__name__)


async def process_monthly_traffic(sessionmaker):
    async with sessionmaker() as session:
        ids = list((await session.scalars(select(TrafficPolicy.id))).all())
    for policy_id in ids:
        async with sessionmaker() as session:
            try:
                await reconcile_policy(session, policy_id)
            except Exception as exc:
                log.warning('event=monthly_traffic_failed policy_id=%s reason=%s', policy_id, type(exc).__name__)


def monthly_usage(usage: SubscriptionUsage, policy) -> SubscriptionUsage:
    if policy is None:
        return usage
    if policy.baseline_upload is None or usage.total != policy.panel_limit_bytes:
        raise ValueError('Monthly allowance is not synchronized')
    if usage.upload < policy.baseline_upload or usage.download < policy.baseline_download:
        raise ValueError('Monthly counters were reset externally')
    return SubscriptionUsage(usage.upload - policy.baseline_upload,
                             usage.download - policy.baseline_download,
                             policy.quota_gb * GIB)
