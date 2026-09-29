import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models.main import Base, BotPaymentOrder, Keys, Payments, Persons, Servers, Location, Vds
from bot.misc.util import CONFIG
from bot.services import bot_payment_orders as orders
from bot.misc.Payment.YooMoney import YooMoney
from bot.misc.VPN.Xui.Vless import Vless


def test_receipt_validation():
    order = SimpleNamespace(id='vb2_test', amount_kopecks=9900)
    receipt = dict(label=order.id, status='success', direction='in', operation_id='op1', amount='96.03')
    assert orders.matches_receipt(order, receipt)
    for fields in ({'label': 'other'}, {'status': 'in_progress'}, {'status': 'refused'},
                   {'direction': 'out'}, {'operation_id': ''}, {'amount': '96.02'},
                   {'amount': 'NaN'}, {'amount': 'Infinity'}, {'unaccepted': True}, {'codepro': 'true'}):
        assert not orders.matches_receipt(order, dict(receipt, **fields))


async def environment(monkeypatch):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Location(id=1, name='Test'))
        await session.flush()
        session.add(Vds(id=1, name='Test', ip='test', max_space=100, location=1))
        await session.flush()
        session.add(Servers(id=1, type_vpn=1, ip='test', work=True, auto_work=True, vds=1, inbound_id=1))
        session.add(Persons(id=1, tgid=123, banned=True, blocked=False, lang='ru'))
        session.add(BotPaymentOrder(id='vb2_test', user_tgid=123, type_pay=0, months=1,
                                  amount_kopecks=9900, protocol=1, location=-1,
                                  created_at=int(time.time()) - 7200, next_attempt=0))
        await session.commit()
    helper = SimpleNamespace(_resolve_server_for_new_key=AsyncMock(return_value=SimpleNamespace(id=1, type_vpn=1)),
                             post_key=AsyncMock(), message=SimpleNamespace(answer=AsyncMock()),
                             _notify_admin_payment=AsyncMock(), _format_expire_date=lambda x: 'date',
                             _resolve_server_name=lambda x: 'server')
    monkeypatch.setattr(orders, 'payment_helper', AsyncMock(return_value=helper))
    monkeypatch.setattr(orders, 'provision_key', AsyncMock(return_value='vless://test'))
    return engine, factory, helper


def test_restart_delayed_payment_panel_failure_and_duplicate_credit(monkeypatch):
    async def scenario():
        engine, factory, helper = await environment(monkeypatch)
        try:
            monkeypatch.setattr(orders, 'find_receipt', AsyncMock(return_value='receipt1'))
            monkeypatch.setattr(orders, 'provision_key', AsyncMock(side_effect=RuntimeError('panel offline')))
            await orders.process_payment_orders(None, factory)
            async with factory() as session:
                order = await session.get(BotPaymentOrder, 'vb2_test')
                assert order.paid_at and not order.fulfilled and order.attempts == 1
                key = await session.get(Keys, order.key_id)
                expiry, key_id = key.subscription, key.id
                assert key.paid_quota_gb == 50
                assert await session.scalar(select(func.count(Payments.id))) == 1
                order.next_attempt = 0
                await session.commit()
            helper.post_key.assert_not_awaited()
            # New session simulates restart; no second receipt lookup or entitlement.
            monkeypatch.setattr(orders, 'find_receipt', AsyncMock(side_effect=AssertionError('must not poll paid order')))
            monkeypatch.setattr(orders, 'provision_key', AsyncMock(return_value='vless://test'))
            await orders.process_payment_orders(None, factory)
            async with factory() as session:
                await orders.credit_order(session, None, 'vb2_test', 'receipt1')
                order = await session.get(BotPaymentOrder, 'vb2_test')
                assert order.completed
                key = await session.get(Keys, key_id)
                assert key.subscription == expiry and key.paid_quota_gb == 50
                assert await session.scalar(select(func.count(Keys.id))) == 1
                assert await session.scalar(select(func.count(Payments.id))) == 1
            helper.post_key.assert_awaited_once()
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_receipt_survives_missing_server_and_telegram_failure(monkeypatch):
    async def scenario():
        engine, factory, helper = await environment(monkeypatch)
        try:
            monkeypatch.setattr(orders, 'find_receipt', AsyncMock(return_value='receipt1'))
            helper._resolve_server_for_new_key.return_value = None
            await orders.process_payment_orders(None, factory)
            async with factory() as session:
                order = await session.get(BotPaymentOrder, 'vb2_test')
                assert order.operation_id == 'receipt1' and not order.paid_at
                order.next_attempt = 0
                await session.commit()
            helper._resolve_server_for_new_key.return_value = SimpleNamespace(id=1, type_vpn=1)
            monkeypatch.setattr(orders, 'find_receipt', AsyncMock(side_effect=AssertionError('receipt already persisted')))
            helper.post_key.side_effect = RuntimeError('Telegram offline')
            await orders.process_payment_orders(None, factory)
            async with factory() as session:
                order = await session.get(BotPaymentOrder, 'vb2_test')
                assert order.fulfilled and not order.user_notified
                assert await session.scalar(select(func.count(Keys.id))) == 1
                order.next_attempt = 0
                await session.commit()
            helper.post_key.side_effect = None
            await orders.process_payment_orders(None, factory)
            async with factory() as session:
                assert (await session.get(BotPaymentOrder, 'vb2_test')).completed
                assert await session.scalar(select(func.count(Payments.id))) == 1
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_renewal_ownership_and_absolute_quota(monkeypatch):
    async def scenario():
        engine, factory, helper = await environment(monkeypatch)
        try:
            async with factory() as session:
                session.add(Keys(id=10, user_tgid=123, server=1, subscription=int(time.time())+1000,
                                 free_key=False, paid_quota_gb=50))
                order = await session.get(BotPaymentOrder, 'vb2_test')
                order.type_pay = 1
                order.requested_key_id = 10
                await session.commit()
                before = (await session.get(Keys, 10)).subscription
                await orders.credit_order(session, None, order.id, 'renew1')
                await orders.credit_order(session, None, order.id, 'renew1')
                key = await session.get(Keys, 10)
                assert key.subscription == before + CONFIG.COUNT_SECOND_MOTH
                assert key.paid_quota_gb == 100
                with pytest.raises(ValueError):
                    await orders.credit_order(session, None, order.id, 'different')
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_current_invoice_parameters():
    from urllib.parse import urlsplit, parse_qs
    payment = object.__new__(YooMoney)
    payment.TOKEN_WALLET = 'wallet'
    payment.price = 99
    payment.ID = 'vb2_test'
    query = parse_qs(urlsplit(asyncio.run(payment.invoice())).query)
    assert query['quickpay-form'] == ['button']
    assert query['paymentType'] == ['AC']
    assert query['sum'] == ['99.00']
    assert query['label'] == ['vb2_test']


def test_panel_rejection_does_not_export_key(monkeypatch):
    client = object.__new__(Vless)
    client.inbound_id = 1
    client.free_server = False
    client.xui = SimpleNamespace(additional_inbound_ids=[2], get_key_vless=AsyncMock())
    async def request(**kwargs):
        if kwargs['endpoint'].endswith('inbounds/list'):
            return {'success': True, 'obj': [{'id': i, 'enable': True, 'settings': {'clients': []}} for i in [1, 2]]}
        return {'success': True, 'obj': []}
    client.xui.request = request
    client.add_client = AsyncMock(return_value=False)
    with pytest.raises(RuntimeError, match='rejected'):
        asyncio.run(client.get_key_user('123.157.vl', 'Test'))
    client.xui.get_key_vless.assert_not_awaited()


def test_panel_retry_preserves_identity_and_attaches_fallback():
    from datetime import datetime, timezone
    from copy import deepcopy
    client = object.__new__(Vless)
    client.inbound_id = 1
    client.free_server = False
    original = dict(id='stable-uuid', email='123.157.vl', enable=True, expiryTime=1,
                    totalGB=50 * 1073741824, security='auto', tgId=0, subId='stable-sub')
    attached = {1: deepcopy(original)}
    calls = []
    async def request(**kwargs):
        calls.append(kwargs['endpoint'])
        if kwargs['endpoint'].endswith('inbounds/list'):
            return {'success': True, 'obj': [dict(id=i, enable=True, settings={'clients': [deepcopy(attached[i])] if i in attached else []}) for i in (1, 2)]}
        if '/update/' in kwargs['endpoint']:
            for i in attached:
                attached[i] = deepcopy(kwargs['json'])
            return {'success': True}
        if kwargs['endpoint'].endswith('/attach'):
            for i in kwargs['json']['inboundIds']:
                attached[i] = deepcopy(attached[1])
            return {'success': True}
        raise AssertionError(kwargs['endpoint'])
    client.xui = SimpleNamespace(additional_inbound_ids=[2], request=request)
    expiry = datetime.fromtimestamp(2000000000, timezone.utc)
    asyncio.run(client.ensure_client('123.157.vl', expire_at=expiry, limit_gb=100))
    count = len(calls)
    asyncio.run(client.ensure_client('123.157.vl', expire_at=expiry, limit_gb=100))
    assert all('update' not in path and 'attach' not in path for path in calls[count:])
    assert set(attached) == {1, 2}
    assert attached[2]['id'] == 'stable-uuid' and attached[2]['subId'] == 'stable-sub'
    assert attached[2]['expiryTime'] == 2000000000000
    assert not any('reset' in path for path in calls)


@pytest.mark.skipif(__import__('os').getenv('PORTAL_TEST_POSTGRES') != '1', reason='isolated PostgreSQL required')
def test_postgres_migration_and_concurrent_confirmations(monkeypatch):
    import importlib.util
    import secrets
    from pathlib import Path
    from sqlalchemy import text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    async def scenario():
        schema = 'payment_test_' + secrets.token_hex(8)
        url = 'postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test'
        admin = create_async_engine(url)
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            path = Path(__file__).parents[1] / 'bot/bot/alembic/versions/20b3c4d5e6f7_bot_payment_orders.py'
            spec = importlib.util.spec_from_file_location('bot_order_migration', path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            def migrate(conn):
                Base.metadata.create_all(conn, tables=[t for t in Base.metadata.sorted_tables if t.name != 'bot_payment_orders'])
                conn.execute(text('ALTER TABLE keys DROP COLUMN paid_quota_gb'))
                migration.op = Operations(MigrationContext.configure(conn))
                migration.upgrade()
            async with engine.begin() as conn:
                await conn.run_sync(migrate)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(Location(id=1, name='Test'))
                await session.flush()
                session.add(Vds(id=1, name='test', ip='test', max_space=100, location=1))
                await session.flush()
                session.add(Servers(id=1, type_vpn=1, vds=1, work=True))
                session.add(Persons(id=1, tgid=123, blocked=False))
                await session.flush()
                session.add(BotPaymentOrder(id='vb2_concurrent', user_tgid=123, type_pay=0, months=1,
                    amount_kopecks=9900, protocol=1, location=-1, created_at=1, next_attempt=0))
                await session.commit()
            helper = SimpleNamespace(_resolve_server_for_new_key=AsyncMock(return_value=SimpleNamespace(id=1, type_vpn=1)))
            monkeypatch.setattr(orders, 'payment_helper', AsyncMock(return_value=helper))
            ready = asyncio.Event()
            loaded_count = 0
            async def confirm():
                nonlocal loaded_count
                async with factory() as session:
                    loaded = await session.get(BotPaymentOrder, 'vb2_concurrent')
                    loaded_count += 1
                    if loaded_count == 6:
                        ready.set()
                    await ready.wait()
                    assert loaded.id == 'vb2_concurrent'
                    await orders.bind_receipt(session, 'vb2_concurrent', 'same-receipt')
                    await orders.credit_order(session, None, 'vb2_concurrent', 'same-receipt')
            await asyncio.gather(*(confirm() for _ in range(6)))
            async with factory() as session:
                assert await session.scalar(select(func.count(Payments.id))) == 1
                assert await session.scalar(select(func.count(Keys.id))) == 1
                key = await session.scalar(select(Keys))
                assert key.paid_quota_gb == 50
                assert abs(key.subscription - int(time.time()) - CONFIG.COUNT_SECOND_MOTH) < 10
            async with engine.begin() as conn:
                def downgrade(conn):
                    migration.op = Operations(MigrationContext.configure(conn))
                    migration.downgrade()
                await conn.run_sync(downgrade)
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())


def test_cannot_renew_another_users_key(monkeypatch):
    async def scenario():
        engine, factory, helper = await environment(monkeypatch)
        try:
            async with factory() as session:
                session.add(Persons(id=2, tgid=456))
                await session.flush()
                session.add(Keys(id=10, user_tgid=456, server=1, subscription=2000000000,
                                 free_key=False, paid_quota_gb=50))
                order = await session.get(BotPaymentOrder, 'vb2_test')
                order.type_pay = 1
                order.requested_key_id = 10
                await session.commit()
                with pytest.raises(ValueError, match='Owned'):
                    await orders.credit_order(session, None, order.id, 'receipt')
                await session.rollback()
                assert await session.scalar(select(func.count(Payments.id))) == 0
                assert (await session.get(Keys, 10)).subscription == 2000000000
        finally:
            await engine.dispose()
    asyncio.run(scenario())
