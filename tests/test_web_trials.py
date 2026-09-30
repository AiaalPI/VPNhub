"""Trial grants survive panel failures and cannot extend themselves on retry."""
import asyncio
import importlib.util
import os
import secrets
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models.main import Base, Location, Servers, Vds
from bot.misc.util import CONFIG
from bot.portal import services, trials
from bot.portal.models import WebAccount, WebOrder, WebSubscription, WebTrial
from bot.portal.security import trial_email_digest
from test_web_portal import config, environment, login


async def provision(session, sub, provision=False):
    sub.provisioned_until = sub.expires_at
    await session.commit()
    return []


def test_trial_failure_retry_expiry_and_no_payment(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        monkeypatch.setattr(CONFIG, "trial_period", 259200)
        calls = []
        async def unavailable(*args, **kwargs):
            raise TimeoutError("panel unavailable")
        async def limiter(*args):
            calls.append(args)
        monkeypatch.setattr(services, "panel_access", unavailable)
        monkeypatch.setattr(services, "rate_limit", limiter)
        try:
            assert (await client.post("/web/api/trial", json={})).status_code == 401
            await login(client, sent)
            assert (await client.post("/web/api/trial", headers={"Origin": "https://evil.test"}, json={})).status_code == 403
            assert (await client.get("/web/api/account")).json()["trial"]["eligible"]
            before = int(time.time())
            assert (await client.post("/web/api/trial", json={})).status_code == 503
            async with factory() as session:
                sub = await session.scalar(select(WebSubscription))
                identity = (sub.id, sub.client_uuid, sub.expires_at, sub.quota_bytes)
                assert before + 259200 <= sub.expires_at <= int(time.time()) + 259200
                assert sub.quota_bytes == 10 * 1073741824
                assert sub.provisioned_until == 0
                assert await session.scalar(select(func.count()).select_from(WebOrder)) == 0
            monkeypatch.setattr(services, "panel_access", provision)
            for _ in range(2):
                assert (await client.post("/web/api/trial", json={})).status_code == 200
            account = (await client.get("/web/api/account")).json()
            assert account["trial"]["used"] and account["trial"]["is_trial"]
            assert not account["trial"]["eligible"]
            assert account["subscription"]["ready"]
            assert len([c for c in calls if c[0].startswith("trial-ip:")]) == 1
            async with factory() as session:
                sub = await session.scalar(select(WebSubscription))
                assert (sub.id, sub.client_uuid, sub.expires_at, sub.quota_bytes) == identity
                trial = await session.scalar(select(WebTrial))
                trial.expires_at = sub.expires_at = int(time.time()) - 1
                await session.commit()
            assert (await client.post("/web/api/trial", json={})).status_code == 409
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_trial_unavailable_server_and_email_aliases(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        monkeypatch.setattr(CONFIG, "trial_period", 259200)
        monkeypatch.setattr(services, "panel_access", provision)
        try:
            await login(client, sent, "some.one+vpn@gmail.com")
            async with factory() as session:
                (await session.get(Servers, 1)).auto_work = False
                await session.commit()
            assert (await client.post("/web/api/trial", json={})).status_code == 503
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(WebTrial)) == 0
                assert await session.scalar(select(func.count()).select_from(WebSubscription)) == 0
                (await session.get(Servers, 1)).auto_work = True
                await session.commit()
            app.state.portal_config = replace(config(), terms_url="")
            assert (await client.post("/web/api/trial", json={})).status_code == 503
            app.state.portal_config = config()
            assert (await client.post("/web/api/trial", json={})).status_code == 200
            await client.post("/web/api/auth/logout", json={})
            await login(client, sent, "someone@googlemail.com")
            assert not (await client.get("/web/api/account")).json()["trial"]["eligible"]
            assert (await client.post("/web/api/trial", json={})).status_code == 409
            assert trial_email_digest("s", "a.b@example.ru") != trial_email_digest("s", "ab@example.ru")
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.parametrize("pay_first", [False, True])
def test_pending_checkout_can_try_and_payment_preserves_identity(monkeypatch, pay_first):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        monkeypatch.setattr(CONFIG, "trial_period", 259200)
        monkeypatch.setattr(services, "panel_access", provision)
        try:
            await login(client, sent)
            response = await client.post("/web/api/orders", json={"months": 1, "accepted_terms": True})
            assert response.status_code == 200
            order_id = response.json()["id"]
            async with factory() as session:
                sub = await session.scalar(select(WebSubscription))
                original_uuid = sub.client_uuid
            if not pay_first:
                assert (await client.post("/web/api/trial", json={})).status_code == 200
            async with factory() as session:
                sub = await session.scalar(select(WebSubscription))
                expiry, quota = sub.expires_at, sub.quota_bytes
                order = await session.get(WebOrder, order_id)
                paid_quota = order.quota_bytes
                await services.apply_payment(session, order_id, "test-payment", 15000)
            async with factory() as session:
                sub = await session.scalar(select(WebSubscription))
                assert sub.client_uuid == original_uuid
                assert sub.expires_at >= max(expiry, int(time.time()) - 1) + int(CONFIG.COUNT_SECOND_MOTH)
                assert sub.quota_bytes == quota + paid_quota
            account = (await client.get("/web/api/account")).json()
            assert not account["trial"]["eligible"] and not account["trial"]["is_trial"]
            if pay_first:
                assert (await client.post("/web/api/trial", json={})).status_code == 409
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.skipif(os.getenv("PORTAL_TEST_POSTGRES") != "1", reason="isolated PostgreSQL required")
def test_postgres_concurrent_trials_and_alias_claims(monkeypatch):
    """Exercise PostgreSQL row locks and the unique alias claim under contention."""
    async def scenario():
        schema = "trial_test_" + secrets.token_hex(8)
        url = "postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test"
        admin = create_async_engine(url)
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        monkeypatch.setattr(CONFIG, "trial_period", 259200)
        monkeypatch.setattr(services, "panel_access", provision)
        async def unlimited(*args):
            pass
        monkeypatch.setattr(services, "rate_limit", unlimited)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            def migrate(connection):
                Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables if not t.name.startswith("web_")])
                for filename in ["10a2b3c4d5e6_add_web_portal.py", "30c4d5e6f7a8_web_trials.py"]:
                    spec = importlib.util.spec_from_file_location("migration", Path(__file__).parents[1] / "bot/bot/alembic/versions" / filename)
                    migration = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(migration)
                    migration.op = Operations(MigrationContext.configure(connection))
                    migration.upgrade()
            async with engine.begin() as conn:
                await conn.run_sync(migrate)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(Location(id=1, name="Test"))
                await session.flush()
                session.add(Vds(id=1, name="test", ip="203.0.113.1", max_space=100, location=1))
                await session.flush()
                session.add(Servers(id=1, type_vpn=CONFIG.TypeVpn.VLESS.value, vds=1, work=True, auto_work=True))
                for name, email in [("one", "one@example.ru"), ("alias-a", "a.b@gmail.com"), ("alias-b", "ab+vpn@googlemail.com")]:
                    session.add(WebAccount(id=name, email=email, created_at=1, disabled=False))
                await session.commit()
            async def activate(account_id):
                async with factory() as session:
                    try:
                        sub = await trials.activate(session, await session.get(WebAccount, account_id), config(), "127.0.0.1")
                        await session.commit()
                        return sub.id, sub.client_uuid, sub.expires_at, sub.quota_bytes
                    except HTTPException as exc:
                        return exc.status_code
            results = await asyncio.gather(*(activate("one") for _ in range(4)))
            assert len(set(results)) == 1 and isinstance(results[0], tuple)
            aliases = await asyncio.gather(activate("alias-a"), activate("alias-b"))
            assert sum(isinstance(result, tuple) for result in aliases) == 1
            assert 409 in aliases
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(WebTrial)) == 2
                assert await session.scalar(select(func.count()).select_from(WebSubscription)) == 2
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())
