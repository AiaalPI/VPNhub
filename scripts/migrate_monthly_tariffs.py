#!/usr/bin/env python3
"""Review, then opt in existing XUI subscribers to monthly traffic allowances.

Run inside the application container with PYTHONPATH=/app. Dry-run is default.
Overrides map key IDs to purchased terms when no key-specific receipt survives.
No passwords, subscription links, or UUIDs are printed. Expiry is never reduced.
"""
import argparse
import asyncio
import json
import time
from datetime import timezone
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.database import engine
from bot.database.models.main import BotPaymentOrder, Keys, Payments, Servers, TrafficPolicy
from bot.misc.VPN.ServerManager import ServerManager
from bot.misc.VPN.Xui.Vless import Vless
from bot.misc.tariffs import get_trial_data_limit_gb
from bot.portal.models import WebOrder, WebSubscription, WebTrial
from bot.services.monthly_traffic_service import configure_policy, process_monthly_traffic, GIB


async def upgrade_trial(session, server_id, email):
    server = await session.get(Servers, server_id)
    manager = ServerManager(server, timeout=8)
    if not isinstance(manager.client, Vless):
        raise ValueError('Trial migration requires XUI VLESS')
    xui = manager.client.xui
    try:
        await manager.login()
        result = await xui.request(method='GET', endpoint='/panel/api/clients/list')
        rows = [r for r in result['obj'] if r['email'] == email] if result.get('success') else []
        if len(rows) != 1 or not rows[0].get('uuid'):
            raise ValueError('Trial client missing or ambiguous')
        row = rows[0]
        old_limit = int(row['totalGB'])
        # Never turn a genuine unlimited trial into a smaller quota here.
        desired = max(old_limit, get_trial_data_limit_gb() * GIB) if old_limit else 0
        if desired == old_limit:
            return
        payload = {k: v for k, v in row.items() if k not in ('id', 'uuid', 'traffic', 'inboundIds', 'createdAt', 'updatedAt')}
        payload['id'] = row['uuid']
        payload['totalGB'] = desired
        used = row['traffic']['up'] + row['traffic']['down']
        payload['enable'] = bool(row['enable']) or (old_limit <= used < desired)
        result = await xui.request(method='POST', endpoint='/panel/api/clients/update/' + quote(email, safe=''), json=payload)
        if not result.get('success'):
            raise ValueError('Trial quota update failed')
        result = await xui.request(method='GET', endpoint='/panel/api/clients/list')
        rows = [r for r in result['obj'] if r['email'] == email] if result.get('success') else []
        if len(rows) != 1 or rows[0]['totalGB'] != desired or rows[0]['uuid'] != row['uuid'] or rows[0]['expiryTime'] != row['expiryTime']:
            raise ValueError('Trial quota verification failed')
    finally:
        await xui.close()


async def run(apply, overrides):
    e = engine()
    factory = async_sessionmaker(e, expire_on_commit=False)
    now = int(time.time())
    try:
        async with factory() as s:
            keys = list((await s.scalars(select(Keys).where(Keys.subscription > now, Keys.free_key.is_(False)))).all())
            plan, unresolved, trials = [], [], []
            for key in keys:
                if key.trial_period:
                    trials.append((key.server, f'{key.user_tgid}.{key.id}.vl'))
                    continue
                orders = list((await s.scalars(select(BotPaymentOrder).where(
                    BotPaymentOrder.key_id == key.id, BotPaymentOrder.paid_at.is_not(None),
                    BotPaymentOrder.type_pay.in_((0, 1))).order_by(BotPaymentOrder.paid_at))).all())
                payment = await s.scalar(select(Payments).where(Payments.id_payment == key.id_payment)) if key.id_payment else None
                months = orders[-1].months if orders else payment.month_count if payment else overrides.get(str(key.id))
                if months not in (1, 3, 6, 12):
                    unresolved.append(key.id)
                    continue
                # For manual grants, start a documented billing cycle at rollout;
                # a historical activation cannot be invented from current expiry.
                anchor = orders[0].paid_at if orders else int(payment.data.replace(tzinfo=timezone.utc).timestamp()) if payment and payment.data else now
                plan.append((key, None, months, anchor))
            subs = list((await s.scalars(select(WebSubscription).where(WebSubscription.expires_at > now))).all())
            for sub in subs:
                orders = list((await s.scalars(select(WebOrder).where(WebOrder.subscription_id == sub.id,
                    WebOrder.paid_at.is_not(None)).order_by(WebOrder.paid_at))).all())
                if orders:
                    plan.append((None, sub, orders[-1].months, orders[0].paid_at))
                elif await s.scalar(select(WebTrial).where(WebTrial.subscription_id == sub.id)):
                    trials.append((sub.server_id, 'web.' + sub.id))
                else:
                    unresolved.append('web:' + sub.id)
            print(json.dumps({'apply': apply, 'paid': [{'key_id': k.id if k else None,
                'web_id': sub.id if sub else None, 'months': months, 'anchor_at': anchor,
                'expires_at': k.subscription if k else sub.expires_at} for k, sub, months, anchor in plan],
                'trial_count': len(trials), 'unresolved': unresolved}), flush=True)
            if not apply:
                return
            if unresolved:
                raise ValueError('Resolve every paid subscription before applying migration')
            for key, sub, months, anchor in plan:
                await configure_policy(s, key=key, sub=sub, months=months, now=now, anchor=anchor)
            for sub in subs:
                if any(email == 'web.' + sub.id for _, email in trials):
                    sub.quota_bytes = get_trial_data_limit_gb() * GIB
            await s.commit()
            # All operations below are idempotent absolute updates. A rerun
            # preserves the existing policy anchor and monthly baseline.
            for server_id, email in trials:
                await upgrade_trial(s, server_id, email)
        await process_monthly_traffic(factory)
        async with factory() as s:
            pending = list((await s.scalars(select(TrafficPolicy.id).where(TrafficPolicy.applied_at.is_(None)))).all())
            if pending:
                raise ValueError('Policies not delivered: ' + ','.join(map(str, pending)))
        print(json.dumps({'migration': 'applied_and_verified'}))
    finally:
        await e.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--key-months', default='{}', help='JSON mapping key ID to 1/3/6/12 months')
    args = parser.parse_args()
    asyncio.run(run(args.apply, json.loads(args.key_months)))
