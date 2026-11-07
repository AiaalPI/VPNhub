import asyncio
import copy
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models.main import Base, BotPaymentOrder, Keys, Location, Persons, Servers, TrafficPolicy, Vds
from bot.misc.util import CONFIG
from bot.portal import services
from bot.portal.models import (SharedSubscription, SharedSubscriptionMember, WebAccount,
    WebOrder, WebSubscription, WebTelegramLink)
from bot.services import bot_payment_orders, shared_subscriptions as shared

GIB = shared.GIB
NOW = 1800000000


class Panel:
    def __init__(self):
        self.rows = {
            '123.7.vl': dict(uuid='old-telegram-uuid', email='123.7.vl', enable=True,
                totalGB=310*GIB, expiryTime=(NOW+10*86400)*1000, reset=0,
                traffic=dict(up=0, down=30*GIB)),
            'web.sub': dict(uuid='old-website-uuid', email='web.sub', enable=True,
                totalGB=620*GIB, expiryTime=(NOW+20*86400)*1000, reset=0,
                traffic=dict(up=0, down=120*GIB))}
        self.fail_after_write = False
        self.writes = 0

    async def login(self, **kwargs):
        pass

    async def close(self):
        pass

    async def request(self, method, endpoint, **kwargs):
        if method == 'GET':
            return {'success': True, 'obj': copy.deepcopy(list(self.rows.values()))}
        email = endpoint.rsplit('/', 1)[1]
        row = self.rows[email]
        assert kwargs['json']['id'] == row['uuid']
        self.writes += 1
        row.update({k:v for k,v in kwargs['json'].items() if k != 'id'})
        if self.fail_after_write:
            self.fail_after_write = False
            raise TimeoutError('lost response')
        return {'success': True}


async def environment(monkeypatch, engine=None):
    engine = engine or create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Location(id=1, name='Test'))
        await session.flush()
        session.add(Vds(id=1, name='Test', ip='test', location=1))
        await session.flush()
        session.add_all([Servers(id=1, type_vpn=1, work=True, ip='test', inbound_id=1, vds=1),
            Persons(id=1, tgid=123, blocked=False), WebAccount(id='account', email='test@example.invalid', created_at=NOW)])
        await session.flush()
        session.add_all([
            WebSubscription(id='sub', account_id='account', server_id=1, client_uuid='old-website-uuid',
                sub_id='a'*32, expires_at=NOW+20*86400, provisioned_until=NOW+20*86400, quota_bytes=600*GIB),
            Keys(id=7, user_tgid=123, server=1, subscription=NOW+10*86400, paid_quota_gb=300)])
        await session.flush()
        session.add(WebTelegramLink(account_id='account', telegram_tgid=123, created_at=NOW))
        session.add_all([
            TrafficPolicy(key_id=7, server_id=1, email='123.7.vl', months=1, quota_gb=300,
                anchor_at=NOW-86400, next_reset_at=NOW+29*86400, baseline_upload=0, baseline_download=10*GIB, panel_limit_bytes=310*GIB),
            TrafficPolicy(web_subscription_id='sub', server_id=1, email='web.sub', months=3, quota_gb=600,
                anchor_at=NOW-86400, next_reset_at=NOW+29*86400, baseline_upload=0, baseline_download=20*GIB, panel_limit_bytes=620*GIB)])
        await session.commit()
    panel = Panel()
    monkeypatch.setattr(shared, 'CompatXUI', lambda **kwargs: panel)
    async def provision(session, sub, **kwargs):
        sub.provisioned_until = sub.expires_at
        return ['fake-profile']
    monkeypatch.setattr(services, 'panel_access', provision)
    monkeypatch.setattr(shared.time, 'time', lambda: NOW)
    monkeypatch.setattr(bot_payment_orders, 'payment_helper', AsyncMock(return_value=SimpleNamespace()))
    return engine, factory, panel


def test_merge_preserves_days_uuids_and_sum_of_remaining_bytes(monkeypatch):
    async def scenario():
        engine, factory, panel = await environment(monkeypatch)
        try:
            async with factory() as s:
                group = await shared.ensure_group(s, 'account', now=NOW)
                assert group.expires_at == NOW+30*86400
                assert group.quota_bytes == 600*GIB
                await s.commit()
            async with factory() as s:
                await shared.ensure_group(s, 'account', now=NOW+1)
                await s.commit()
                await shared.reconcile(s, 'account', now=NOW)
                group = await s.get(SharedSubscription, 'account')
                assert group.expires_at == NOW+30*86400  # no repeated grant
                assert group.allowance_bytes == 780*GIB  # 280 + 500
                assert (await shared.usage(s, 'account')).total == 780*GIB
                assert (await s.get(Keys,7)).subscription == (await s.get(WebSubscription,'sub')).expires_at == group.expires_at
            assert [r['uuid'] for r in panel.rows.values()] == ['old-telegram-uuid', 'old-website-uuid']
            panel.rows['123.7.vl']['traffic']['down'] += 50*GIB
            panel.rows['web.sub']['traffic']['down'] += 730*GIB
            async with factory() as s:
                await shared.reconcile(s, 'account', now=NOW+10)
                usage = await shared.usage(s, 'account')
                assert usage.download == usage.total == 780*GIB
            assert all(not row['enable'] for row in panel.rows.values())
            async with factory() as s:
                group = await s.get(SharedSubscription, 'account')
                boundary = group.next_reset_at
                await shared.reconcile(s, 'account', now=boundary)
                usage = await shared.usage(s, 'account')
                assert usage.download == 0 and usage.total == 600*GIB
            # The original 30 paid days may end before the calendar boundary.
            assert all(not row['enable'] for row in panel.rows.values())
            async with factory() as s:
                group = await s.get(SharedSubscription, 'account')
                await shared.renew(s, group, 3, now=boundary)
                await s.commit()
                await shared.reconcile(s, 'account', now=boundary)
                assert (await shared.usage(s, 'account')).total == 600*GIB
            assert all(row['enable'] for row in panel.rows.values())
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_lost_panel_response_and_external_counter_reset_do_not_grant_again(monkeypatch):
    async def scenario():
        engine, factory, panel = await environment(monkeypatch)
        try:
            panel.fail_after_write = True
            async with factory() as s:
                with pytest.raises(TimeoutError):
                    await shared.reconcile(s, 'account', now=NOW)
            panel.rows['123.7.vl']['traffic']['down'] += GIB
            async with factory() as s:
                await shared.reconcile(s, 'account', now=NOW+5)
                usage = await shared.usage(s, 'account')
                assert usage.download == GIB and usage.total == 780*GIB
            panel.rows['123.7.vl']['traffic']['down'] = 0
            async with factory() as s:
                with pytest.raises(ValueError, match='reset externally'):
                    await shared.reconcile(s, 'account', now=NOW+10)
                await s.rollback()
                assert (await s.get(SharedSubscription,'account')).allowance_bytes == 780*GIB
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_both_payment_channels_extend_one_entitlement_exactly_once(monkeypatch):
    async def scenario():
        engine, factory, panel = await environment(monkeypatch)
        try:
            async with factory() as s:
                await shared.ensure_group(s,'account',now=NOW)
                s.add(WebOrder(id='web-order',account_id='account',subscription_id='sub',months=1,
                    amount_kopecks=10000,quota_bytes=300*GIB,created_at=NOW))
                s.add(BotPaymentOrder(id='bot-order',user_tgid=123,type_pay=0,months=3,
                    amount_kopecks=20000,protocol=1,location=1,created_at=NOW,next_attempt=NOW))
                await s.commit()
                await services.apply_payment(s,'web-order','web-receipt',10000)
                await services.apply_payment(s,'web-order','web-receipt',10000)
                await bot_payment_orders.credit_order(s,None,'bot-order','bot-receipt')
                await bot_payment_orders.credit_order(s,None,'bot-order','bot-receipt')
                group = await s.get(SharedSubscription,'account',populate_existing=True)
                assert group.expires_at == NOW+30*86400+4*CONFIG.COUNT_SECOND_MOTH
                assert (await s.get(Keys,7)).subscription == (await s.get(WebSubscription,'sub')).expires_at == group.expires_at
                assert len(list((await s.scalars(select(Keys))).all())) == 1
                assert (await s.get(BotPaymentOrder,'bot-order')).key_id == 7
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_trial_days_excluded_and_unlimited_has_priority(monkeypatch):
    async def scenario():
        engine, factory, panel = await environment(monkeypatch)
        try:
            async with factory() as s:
                key=await s.get(Keys,7)
                key.trial_period=True
                await s.commit()
                group=await shared.ensure_group(s,'account',now=NOW)
                assert group.expires_at == NOW+20*86400
                assert len(await shared.members(s,'account')) == 2  # trial UUID kept, days excluded
                await s.rollback()
                key=await s.get(Keys,7); key.trial_period=False; key.paid_quota_gb=0
                p=await s.scalar(select(TrafficPolicy).where(TrafficPolicy.key_id==7));p.quota_gb=0
                await s.commit()
                await shared.reconcile(s,'account',now=NOW)
                group=await s.get(SharedSubscription,'account')
                assert group.quota_bytes==0 and group.allowance_bytes==-1
                assert (await shared.usage(s,'account')).total==0
                assert all(row['totalGB']==0 for row in panel.rows.values())
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_open_private_telegram_view_is_edited_after_renewal(monkeypatch):
    async def scenario():
        from bot.handlers.account import show_account, refresh_account_message
        from bot.portal.config import PortalConfig
        engine, factory, _ = await environment(monkeypatch)
        monkeypatch.setattr(PortalConfig, 'from_env', lambda: SimpleNamespace(enabled=True,origin='https://site.example'))
        message=SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(message_id=42,chat=SimpleNamespace(id=123))))
        bot=SimpleNamespace(edit_message_text=AsyncMock(),send_message=AsyncMock())
        try:
            async with factory() as s:
                group=await shared.ensure_group(s,'account',now=NOW)
                await s.commit()
                await show_account(message,s,123,'ru')
                await s.commit()
                await refresh_account_message(bot,s,'account')
                bot.edit_message_text.assert_not_awaited()
                await shared.renew(s,group,1,now=NOW)
                await s.commit()
                await refresh_account_message(bot,s,'account')
                bot.edit_message_text.assert_awaited_once()
                args=bot.edit_message_text.call_args
                assert args.kwargs['chat_id']==123 and args.kwargs['message_id']==42
                assert 'Единая подписка' in args.args[0] and 'portal_' not in args.args[0]
                bot.send_message.assert_not_awaited()
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_upgrade_before_first_sync_and_pinned_identity(monkeypatch):
    async def scenario():
        engine,factory,panel=await environment(monkeypatch)
        try:
            async with factory() as s:
                group=await shared.ensure_group(s,'account',now=NOW)
                await shared.renew(s,group,6,now=NOW)
                await s.commit()
                await shared.reconcile(s,'account',now=NOW)
                # 780 remaining from the merge + 400 upgrade, no second grant.
                assert (await shared.usage(s,'account')).total==1180*GIB
                assert (await s.get(SharedSubscription,'account')).quota_bytes==1000*GIB
            panel.rows['123.7.vl']['uuid']='unexpected-replacement'
            async with factory() as s:
                with pytest.raises(ValueError,match='UUID changed externally'):
                    await shared.reconcile(s,'account',now=NOW+5)
        finally:
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.skipif(__import__('os').getenv('PORTAL_TEST_POSTGRES') != '1', reason='isolated PostgreSQL required')
def test_postgres_migration_and_cross_channel_concurrent_renewals(monkeypatch):
    import importlib.util
    import secrets
    from pathlib import Path
    from sqlalchemy import text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    async def scenario():
        schema = 'shared_test_' + secrets.token_hex(8)
        url = 'postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test'
        admin = create_async_engine(url)
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            path = Path(__file__).parents[1] / 'bot/bot/alembic/versions/70a8b9c0d1e2_shared_subscriptions.py'
            spec = importlib.util.spec_from_file_location('shared_migration', path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            def migrate(connection):
                Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables
                    if t.name not in ('shared_subscriptions', 'shared_subscription_members', 'web_account_messages')])
                migration.op = Operations(MigrationContext.configure(connection))
                migration.upgrade()
            async with engine.begin() as connection:
                await connection.run_sync(migrate)
            _, factory, _ = await environment(monkeypatch, engine)
            async with factory() as s:
                await shared.ensure_group(s,'account',now=NOW)
                s.add(WebOrder(id='web-order',account_id='account',subscription_id='sub',months=1,
                    amount_kopecks=10000,quota_bytes=300*GIB,created_at=NOW))
                s.add(BotPaymentOrder(id='bot-order',user_tgid=123,type_pay=0,months=3,
                    amount_kopecks=20000,protocol=1,location=1,created_at=NOW,next_attempt=NOW))
                await s.commit()
            async def website():
                async with factory() as s:
                    await services.apply_payment(s,'web-order','web-receipt',10000)
            async def telegram():
                async with factory() as s:
                    await bot_payment_orders.credit_order(s,None,'bot-order','bot-receipt')
            await asyncio.wait_for(asyncio.gather(website(),telegram(),website(),telegram()),timeout=15)
            async with factory() as s:
                group = await s.get(SharedSubscription,'account')
                assert group.expires_at == NOW+30*86400+4*CONFIG.COUNT_SECOND_MOTH
                assert (await s.get(Keys,7)).subscription == (await s.get(WebSubscription,'sub')).expires_at == group.expires_at
                assert len(await shared.members(s,'account'))==2
        finally:
            await engine.dispose()
            async with admin.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())
