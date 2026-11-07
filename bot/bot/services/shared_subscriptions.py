"""Verified cross-channel entitlement, with preserved panel identities.

Account row locks serialize linking and both payment channels. Network writes
are retried from committed absolute entitlements; they never grant paid days.
Global panel counters are summed once per identity, never per transport.
"""
import logging
import secrets
import time
import uuid
from urllib.parse import quote

from sqlalchemy import select

from bot.database.models.main import Keys, Persons, Servers, TrafficPolicy
from bot.misc.tariffs import get_paid_data_limit_gb
from bot.misc.util import CONFIG
from bot.misc.VPN.Xui.CompatXUI import CompatXUI
from bot.portal.models import (SharedSubscription, SharedSubscriptionMember, WebAccount,
                              WebOrder, WebSubscription, WebTelegramLink)
from bot.services.monthly_traffic_service import GIB, next_month_boundary
from bot.services.subscription_usage_service import SubscriptionUsage, usage_from_global_clients

log = logging.getLogger(__name__)


async def lock_account(session, *, account_id=None, telegram_id=None, allow_disabled=False):
    if account_id is None:
        account_id = await session.scalar(select(WebTelegramLink.account_id).where(
            WebTelegramLink.telegram_tgid == telegram_id))
    if account_id is None:
        return None
    account = await session.scalar(select(WebAccount).where(WebAccount.id == account_id)
        .with_for_update().execution_options(populate_existing=True))
    if account is None or (account.disabled and not allow_disabled):
        raise ValueError('Linked account unavailable')
    return account


async def members(session, account_id):
    return list((await session.execute(select(SharedSubscriptionMember, TrafficPolicy)
        .join(TrafficPolicy, TrafficPolicy.id == SharedSubscriptionMember.policy_id)
        .where(SharedSubscriptionMember.account_id == account_id)
        .order_by(TrafficPolicy.id).execution_options(populate_existing=True))).all())


async def group_for_key(session, key_id):
    return await session.scalar(select(SharedSubscription).join(SharedSubscriptionMember)
        .join(TrafficPolicy, TrafficPolicy.id == SharedSubscriptionMember.policy_id)
        .where(TrafficPolicy.key_id == key_id))


async def add_member(session, group, *, key=None, sub=None, contributes=False):
    clause = TrafficPolicy.key_id == key.id if key is not None else TrafficPolicy.web_subscription_id == sub.id
    policy = await session.scalar(select(TrafficPolicy).where(clause).with_for_update())
    quota = (key.paid_quota_gb if key is not None else sub.quota_bytes // GIB)
    # Unknown historical quotas must be reviewed, never silently made unlimited.
    if quota is None and contributes:
        raise ValueError('Historical quota requires explicit migration')
    quota = quota or 0
    if policy is None:
        policy = TrafficPolicy(key_id=key.id if key is not None else None,
            web_subscription_id=sub.id if sub is not None else None,
            server_id=key.server if key is not None else sub.server_id,
            email=f'{key.user_tgid}.{key.id}.vl' if key is not None else 'web.' + sub.id,
            months=1, quota_gb=quota, anchor_at=group.anchor_at,
            next_reset_at=group.next_reset_at)
        session.add(policy)
        await session.flush()
    server = await session.get(Servers, policy.server_id)
    if not server or server.type_vpn != CONFIG.TypeVpn.VLESS.value:
        raise ValueError('Shared subscriptions require XUI VLESS identities')
    if await session.get(SharedSubscriptionMember, policy.id):
        return
    session.add(SharedSubscriptionMember(policy_id=policy.id, account_id=group.account_id,
        contributes=contributes, original_quota=policy.quota_gb * GIB,
        original_expiry=int((key.subscription if key is not None else sub.expires_at) or 0),
        original_reset_at=policy.next_reset_at,
        original_upload=policy.baseline_upload, original_download=policy.baseline_download))
    # Newly provisioned aliases start with one byte, not an extra full allowance.
    if not contributes and policy.panel_limit_bytes is None:
        policy.panel_limit_bytes = 1
    await session.flush()


async def ensure_group(session, account_id, *, now=None, force=False):
    """Idempotent DB-only merge, in the caller's transaction. Never commits."""
    now = int(time.time()) if now is None else now
    account = await lock_account(session, account_id=account_id)
    link = await session.get(WebTelegramLink, account_id)
    if not link:
        return None
    person = await session.scalar(select(Persons).where(Persons.tgid == link.telegram_tgid).with_for_update())
    if not person or person.blocked:
        raise ValueError('Linked account unavailable')
    group = await session.get(SharedSubscription, account_id, populate_existing=True)
    if group:
        return group
    keys = list((await session.scalars(select(Keys).where(Keys.user_tgid == person.tgid,
        Keys.free_key.is_(False)).order_by(Keys.id).with_for_update())).all())
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.account_id == account.id).with_for_update())
    web_paid = bool(sub and await session.scalar(select(WebOrder.id).where(
        WebOrder.subscription_id == sub.id, WebOrder.paid_at.is_not(None)).limit(1)))
    # A managed monthly policy also identifies a previously migrated paid grant.
    web_paid = web_paid or bool(sub and await session.scalar(select(TrafficPolicy.id).where(
        TrafficPolicy.web_subscription_id == sub.id)))
    active = [key for key in keys if not key.trial_period and (key.subscription or 0) > now]
    active_web = bool(web_paid and sub.expires_at > now)
    if not active and not active_web and not force:
        return None
    if not sub:
        if not keys:
            return None
        sub = WebSubscription(id=str(uuid.uuid4()), account_id=account_id, server_id=keys[0].server,
            client_uuid=str(uuid.uuid4()), sub_id=secrets.token_hex(16), expires_at=0,
            quota_bytes=0, provisioned_until=0)
        session.add(sub)
        await session.flush()
    quotas = [key.paid_quota_gb for key in active]
    if any(q is None for q in quotas):
        raise ValueError('Historical quota requires explicit migration')
    if active_web:
        quotas.append(sub.quota_bytes // GIB)
    quota = (0 if 0 in quotas else max(quotas, default=300)) * GIB
    expiry = now + sum(key.subscription - now for key in active) + (sub.expires_at - now if active_web else 0)
    group = SharedSubscription(account_id=account_id, expires_at=expiry, quota_bytes=quota,
        anchor_at=now, next_reset_at=next_month_boundary(now, now), merged_at=now)
    session.add(group)
    await session.flush()
    for key in keys:
        await add_member(session, group, key=key, contributes=key in active)
    await add_member(session, group, sub=sub, contributes=active_web)
    await mirror(session, group)
    return group


async def mirror(session, group):
    """Legacy records are adapters; every renewal writes the same expiry."""
    for member, policy in await members(session, group.account_id):
        policy.quota_gb = group.quota_bytes // GIB
        if policy.key_id:
            key = await session.get(Keys, policy.key_id)
            key.subscription, key.paid_quota_gb = group.expires_at, policy.quota_gb
            key.trial_period = False
            key.notion_oneday = key.notified_1day = key.notified_3days = key.notified_expired = False
        else:
            sub = await session.get(WebSubscription, policy.web_subscription_id)
            sub.expires_at, sub.quota_bytes = group.expires_at, group.quota_bytes
    group.applied_at = None


async def renew(session, group, months, *, now=None):
    now = int(time.time()) if now is None else now
    expired = group.expires_at <= now
    previous = group.quota_bytes
    quota = get_paid_data_limit_gb(months) * GIB
    group.expires_at = max(group.expires_at, now) + months * CONFIG.COUNT_SECOND_MOTH
    group.quota_bytes = quota
    if expired:
        group.pending_bonus_bytes = 0
        group.anchor_at = now
        group.next_reset_at = next_month_boundary(now, now)
        group.allowance_bytes = quota if quota else -1
        for member, policy in await members(session, group.account_id):
            member.baseline_upload = member.baseline_download = None
            member.contributes = False
    elif group.allowance_bytes is None:
        if quota == 0:
            group.allowance_bytes = -1
        elif previous > 0:
            group.pending_bonus_bytes += max(quota - previous, 0)
    else:
        # Renewals never consume a preserved merge bonus or reset used bytes.
        if quota == 0:
            group.allowance_bytes = -1
        elif previous > 0 and group.allowance_bytes >= 0:
            group.allowance_bytes += max(quota - previous, 0)
    await mirror(session, group)


async def extend_key_seconds(session, key, seconds, *, replace=False):
    """Admin/referral extensions use the same entitlement, never one alias."""
    group = await group_for_key(session, key.id)
    if not group:
        return False
    await lock_account(session, account_id=group.account_id)
    group = await session.get(SharedSubscription, group.account_id, populate_existing=True)
    now = int(time.time())
    group.expires_at = (now if replace else max(group.expires_at, now)) + int(seconds)
    await mirror(session, group)
    return True


async def panel_snapshots(session, rows):
    """One authenticated request per server; no customer credentials in logs."""
    result = {}
    for server_id in sorted({policy.server_id for _, policy in rows}):
        server = await session.get(Servers, server_id)
        if not server or not server.work:
            raise ValueError('Shared subscription server unavailable')
        panel = CompatXUI(full_address=('https://' if server.connection_method else 'http://') + server.ip,
            panel='sanaei', https=server.connection_method, timeout=8)
        try:
            await panel.login(username=server.login, password=server.password)
            response = await panel.request(method='GET', endpoint='/panel/api/clients/list')
            for member, policy in rows:
                if policy.server_id != server_id:
                    continue
                usage = usage_from_global_clients(response, policy.email)
                row = next(r for r in response['obj'] if r['email'] == policy.email)
                if not row.get('uuid'):
                    raise ValueError('Missing shared client identity')
                if member.client_uuid and row['uuid'] != member.client_uuid:
                    raise ValueError('Shared client UUID changed externally')
                if policy.web_subscription_id:
                    sub = await session.get(WebSubscription, policy.web_subscription_id)
                    if row['uuid'] != sub.client_uuid:
                        raise ValueError('Shared client UUID mismatch')
                result[policy.id] = (row, usage)
        finally:
            await panel.close()
    return result


def aggregate(group, rows, snapshots):
    upload = download = 0
    for member, policy in rows:
        usage = snapshots[policy.id][1]
        if member.baseline_upload is None:
            raise ValueError('Shared counters not initialized')
        if usage.upload < member.baseline_upload or usage.download < member.baseline_download:
            raise ValueError('Shared panel counters reset externally')
        upload += usage.upload - member.baseline_upload
        download += usage.download - member.baseline_download
    # Client formats use total=0 for unlimited and cannot represent a depleted
    # zero-byte finite grant. Report 1/1 byte while keeping enforcement at zero.
    return SubscriptionUsage(upload + (1 if group.allowance_bytes == 0 else 0), download,
        0 if group.allowance_bytes == -1 else max(group.allowance_bytes, 1))


async def usage(session, account_id):
    group = await session.get(SharedSubscription, account_id, populate_existing=True)
    if not group or group.allowance_bytes is None:
        raise ValueError('Shared allowance not ready')
    rows = await members(session, account_id)
    return aggregate(group, rows, await panel_snapshots(session, rows))


async def reconcile(session, account_id, *, now=None):
    """Sum all aliases and enforce one budget. Counter failures never reset it.

    Enforcement is polling-based (15s), as panel counters are not transactional
    across UUIDs. Each alias ceiling is also capped at the group's remaining
    budget. The small in-flight polling overrun is accounted at the next tick.
    """
    from bot.portal.services import panel_access
    now = int(time.time()) if now is None else now
    account = await lock_account(session, account_id=account_id, allow_disabled=True)
    group = await session.get(SharedSubscription, account_id, populate_existing=True)
    if group is None:
        group = await ensure_group(session, account_id, now=now)
    if group is None:
        await session.commit()
        return
    sub = await session.scalar(select(WebSubscription).where(WebSubscription.account_id == account_id))
    person = await session.scalar(select(Persons).join(WebTelegramLink, WebTelegramLink.telegram_tgid == Persons.tgid)
        .where(WebTelegramLink.account_id == account_id))
    available = not account.disabled and person is not None and not person.blocked
    if available and group.expires_at > now and sub.provisioned_until < sub.expires_at:
        # No commits inside the group lock: panel_access supports this mode.
        await panel_access(session, sub, provision=True, commit=False)
    rows = await members(session, account_id)
    snapshots = await panel_snapshots(session, rows)
    if group.allowance_bytes is None:
        remaining, unlimited = 0, False
        for member, policy in rows:
            counter = snapshots[policy.id][1]
            if member.contributes:
                if member.original_quota == 0:
                    unlimited = True
                else:
                    # Legacy grants without a baseline use their original quota.
                    consumed = counter.upload + counter.download
                    if member.original_reset_at <= group.merged_at:
                        remaining += member.original_quota
                    elif member.original_upload is not None:
                        if counter.upload < member.original_upload or counter.download < member.original_download:
                            raise ValueError('Pre-merge panel counters reset externally')
                        consumed -= member.original_upload + member.original_download
                        remaining += max(member.original_quota - consumed, 0)
                    else:
                        remaining += max(member.original_quota - consumed, 0)
            member.baseline_upload, member.baseline_download = counter.upload, counter.download
        group.allowance_bytes = -1 if unlimited else remaining + group.pending_bonus_bytes
        group.pending_bonus_bytes = 0
    if now >= group.next_reset_at:
        group.allowance_bytes = group.quota_bytes if group.quota_bytes else -1
        group.next_reset_at = next_month_boundary(group.anchor_at, now)
        for member, policy in rows:
            counter = snapshots[policy.id][1]
            member.baseline_upload, member.baseline_download = counter.upload, counter.download
    for member, policy in rows:
        if member.client_uuid is None:
            member.client_uuid = snapshots[policy.id][0]['uuid']
        if member.baseline_upload is None:  # paid reactivation/new alias
            counter = snapshots[policy.id][1]
            member.baseline_upload, member.baseline_download = counter.upload, counter.download
    used = aggregate(group, rows, snapshots)
    remaining = max(group.allowance_bytes - used.upload - used.download, 0)
    # Persist baselines before remote writes. Retrying uses exactly this budget.
    await session.commit()
    account = await lock_account(session, account_id=account_id, allow_disabled=True)
    person = await session.scalar(select(Persons).join(WebTelegramLink, WebTelegramLink.telegram_tgid == Persons.tgid)
        .where(WebTelegramLink.account_id == account_id).execution_options(populate_existing=True))
    available = not account.disabled and person is not None and not person.blocked
    group = await session.get(SharedSubscription, account_id, populate_existing=True)
    rows = await members(session, account_id)
    snapshots = await panel_snapshots(session, rows)
    used = aggregate(group, rows, snapshots)
    remaining = max(group.allowance_bytes - used.upload - used.download, 0)
    for member, policy in rows:
        row, counter = snapshots[policy.id]
        server = await session.get(Servers, policy.server_id)
        panel = CompatXUI(full_address=('https://' if server.connection_method else 'http://') + server.ip,
            panel='sanaei', https=server.connection_method, timeout=8)
        enabled = available and group.expires_at > now and (group.allowance_bytes == -1 or remaining > 0)
        ceiling = 0 if group.allowance_bytes == -1 else max(counter.upload + counter.download + remaining, 1)
        payload = {k: v for k, v in row.items() if k not in ('id', 'uuid', 'traffic', 'inboundIds', 'createdAt', 'updatedAt')}
        payload.update(id=row['uuid'], totalGB=ceiling, expiryTime=group.expires_at * 1000,
                       enable=enabled, reset=0)
        try:
            await panel.login(username=server.login, password=server.password)
            if any(row.get(k) != payload[k] for k in ('totalGB', 'expiryTime', 'enable', 'reset')):
                response = await panel.request(method='POST', endpoint='/panel/api/clients/update/' + quote(policy.email, safe=''), json=payload)
                if not response.get('success'):
                    raise ValueError('Shared quota update rejected')
                verified = await panel.request(method='GET', endpoint='/panel/api/clients/list')
                usage_from_global_clients(verified, policy.email)
                actual = next(r for r in verified['obj'] if r['email'] == policy.email)
                if actual.get('uuid') != row['uuid'] or any(actual.get(k) != payload[k] for k in ('totalGB', 'expiryTime', 'enable', 'reset')):
                    raise ValueError('Shared quota update verification failed')
            policy.panel_limit_bytes = ceiling
        finally:
            await panel.close()
    group.applied_at = now
    await session.commit()


async def process_shared_subscriptions(sessionmaker, bot=None):
    async with sessionmaker() as session:
        ids = list((await session.scalars(select(WebTelegramLink.account_id))).all())
    for account_id in ids:
        async with sessionmaker() as session:
            try:
                await reconcile(session, account_id)
            except Exception as exc:
                await session.rollback()
                log.warning('event=shared_subscription_sync_failed reason=%s', type(exc).__name__)
            from bot.handlers.account import try_refresh_account_message
            await try_refresh_account_message(bot, session, account_id)
