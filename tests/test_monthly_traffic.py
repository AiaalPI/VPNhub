import asyncio
import copy
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models.main import Base, Keys, Location, Persons, Servers, TrafficPolicy, Vds
from bot.misc.tariffs import get_paid_data_limit_gb, get_trial_data_limit_gb
from bot.services import monthly_traffic_service as service
from bot.services.subscription_usage_service import SubscriptionUsage


def stamp(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=service.BILLING_ZONE).timestamp())


def test_calendar_month_boundaries_and_tariffs():
    anchor = stamp('2028-01-31T10:15:00')
    assert service.next_month_boundary(anchor, anchor) == stamp('2028-02-29T10:15:00')
    assert service.next_month_boundary(anchor, stamp('2028-02-29T10:15:00')) == stamp('2028-03-31T10:15:00')
    assert service.next_month_boundary(anchor, stamp('2029-02-28T10:15:00')) == stamp('2029-03-31T10:15:00')
    assert [get_paid_data_limit_gb(m) for m in (1, 3, 6, 12)] == [300, 600, 1000, 0]
    assert get_trial_data_limit_gb() == 50


class Panel:
    def __init__(self):
        self.row = dict(email='123.7.vl', uuid='stable-uuid', id=99, totalGB=100 * service.GIB,
                        enable=True, expiryTime=stamp('2030-01-01T00:00:00') * 1000,
                        reset=0, flow='xtls-rprx-vision', subId='stable-sub', inboundIds=[1, 2],
                        traffic=dict(up=4 * service.GIB, down=6 * service.GIB))
        self.fail_after_write = False
        self.writes = 0
        self.close = AsyncMock()

    async def request(self, method, endpoint, **kwargs):
        if method == 'GET':
            return dict(success=True, obj=[copy.deepcopy(self.row)])
        assert endpoint == '/panel/api/clients/update/123.7.vl'
        payload = kwargs['json']
        assert payload['id'] == self.row['uuid']
        self.writes += 1
        self.row.update({k: v for k, v in payload.items() if k != 'id'})
        if self.fail_after_write:
            self.fail_after_write = False
            raise TimeoutError('response lost after panel applied request')
        return dict(success=True)


async def environment(monkeypatch, engine=None):
    engine = engine or create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add_all([Location(id=1, name='Test'), Vds(id=1, name='Test', ip='test', location=1),
                   Servers(id=1, type_vpn=1, vds=1, work=True, inbound_id=1),
                   Persons(id=1, tgid=123, blocked=False),
                   Keys(id=7, user_tgid=123, server=1, trial_period=False, free_key=False,
                        subscription=stamp('2030-01-01T00:00:00'))])
        await s.commit()
        key = await s.get(Keys, 7)
        p = await service.configure_policy(s, key=key, months=3, now=stamp('2028-01-31T10:15:00'))
        await s.commit()
        policy_id = p.id
    panel = Panel()
    monkeypatch.setattr(service, 'Vless', SimpleNamespace)
    monkeypatch.setattr(service, 'ServerManager', lambda *a, **kw: SimpleNamespace(
        client=SimpleNamespace(xui=panel), login=AsyncMock()))
    return engine, factory, policy_id, panel


def test_rollover_no_accumulation_and_lost_response_retry(monkeypatch):
    async def scenario():
        engine, factory, pid, panel = await environment(monkeypatch)
        try:
            panel.fail_after_write = True
            async with factory() as s:
                with pytest.raises(TimeoutError):
                    await service.reconcile_policy(s, pid, now=stamp('2028-01-31T10:15:00'))
            # New session/process: preserve the first durable baseline after a
            # successful panel write whose HTTP response was lost.
            panel.row['traffic']['down'] += service.GIB
            async with factory() as s:
                await service.reconcile_policy(s, pid, now=stamp('2028-02-01T10:15:00'))
                p = await s.get(TrafficPolicy, pid)
                assert p.baseline_download == 6 * service.GIB
                assert panel.row['totalGB'] == 610 * service.GIB
                usage = service.monthly_usage(SubscriptionUsage(4 * service.GIB, 7 * service.GIB, panel.row['totalGB']), p)
                assert usage == SubscriptionUsage(0, service.GIB, 600 * service.GIB)
            assert panel.writes == 1
            # Several missed months grant one current monthly allowance.
            panel.row['traffic']['down'] = 606 * service.GIB
            panel.row['enable'] = False  # exhausted old 610 GiB ceiling
            async with factory() as s:
                await service.reconcile_policy(s, pid, now=stamp('2028-05-31T10:15:00'))
                p = await s.get(TrafficPolicy, pid)
                assert p.next_reset_at == stamp('2028-06-30T10:15:00')
                assert panel.row['totalGB'] == 1210 * service.GIB
                assert panel.row['enable'] is True
                assert panel.row['traffic']['down'] == 606 * service.GIB
                assert panel.row['expiryTime'] == stamp('2030-01-01T00:00:00') * 1000
        finally:
            await engine.dispose()
    asyncio.run(scenario())


def test_unlimited_renewal_and_manual_disable_are_preserved(monkeypatch):
    async def scenario():
        engine, factory, pid, panel = await environment(monkeypatch)
        try:
            async with factory() as s:
                await service.reconcile_policy(s, pid, now=stamp('2028-01-31T10:15:00'))
                key = await s.get(Keys, 7)
                p = await service.configure_policy(s, key=key, months=12, now=stamp('2028-02-10T10:15:00'))
                assert p.baseline_download == 6 * service.GIB
                await s.commit()
            panel.row['enable'] = False  # hand-disabled while under quota
            async with factory() as s:
                await service.reconcile_policy(s, pid, now=stamp('2028-02-10T10:15:00'))
                assert panel.row['totalGB'] == 0
                assert panel.row['enable'] is False
                p = await s.get(TrafficPolicy, pid)
                assert p.anchor_at == stamp('2028-01-31T10:15:00')
                assert service.monthly_usage(SubscriptionUsage(4 * service.GIB, 6 * service.GIB, 0), p).total == 0
            async with factory() as s:
                assert await service.reconcile_policy(s, pid, now=stamp('2030-01-01T00:00:00')) is False
        finally:
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.skipif(__import__('os').getenv('PORTAL_TEST_POSTGRES') != '1', reason='isolated PostgreSQL required')
def test_postgres_monthly_migration_and_concurrent_rollover(monkeypatch):
    import importlib.util
    import secrets
    from pathlib import Path
    from sqlalchemy import text
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    async def scenario():
        schema = 'monthly_test_' + secrets.token_hex(8)
        url = 'postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test'
        admin = create_async_engine(url)
        engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            path = Path(__file__).parents[1] / 'bot/bot/alembic/versions/60f7a8b9c0d1_monthly_traffic_policies.py'
            spec = importlib.util.spec_from_file_location('monthly_migration', path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            def migrate(conn):
                Base.metadata.create_all(conn, tables=[t for t in Base.metadata.sorted_tables if t.name not in ('traffic_policies', 'shared_subscription_members')])
                migration.op = Operations(MigrationContext.configure(conn))
                migration.upgrade()
            async with engine.begin() as conn:
                await conn.run_sync(migrate)
            _, factory, pid, panel = await environment(monkeypatch, engine=engine)
            async def reconcile(now):
                async with factory() as session:
                    await service.reconcile_policy(session, pid, now=now)
            await asyncio.gather(*(reconcile(stamp('2028-01-31T10:15:00')) for _ in range(6)))
            assert panel.writes == 1
            panel.row['traffic']['down'] += 20 * service.GIB
            await asyncio.gather(*(reconcile(stamp('2028-02-29T10:15:00')) for _ in range(6)))
            assert panel.writes == 2
            async with factory() as session:
                policy = await session.get(TrafficPolicy, pid)
                assert policy.baseline_download == 26 * service.GIB
                assert panel.row['totalGB'] == 630 * service.GIB
            async with engine.begin() as conn:
                def downgrade(conn):
                    Base.metadata.tables['shared_subscription_members'].drop(conn, checkfirst=True)
                    migration.op = Operations(MigrationContext.configure(conn))
                    migration.downgrade()
                await conn.run_sync(downgrade)
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())
