import asyncio
import hashlib
import hmac
import os
import secrets
import time
from types import SimpleNamespace
from dataclasses import replace
from urllib.parse import quote, urlencode

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot.database.models.main import Base, Location, Servers, Vds
from bot.misc.util import CONFIG
from bot.portal import services
from bot.portal.config import PortalConfig
from bot.portal.models import WebAccount, WebChallenge, WebOrder, WebSession, WebSubscription, WebTrial
from bot.portal.routes import COOKIE, router
from bot.portal.security import code_digest, digest, normalize_email, paid_amount, verify_notification


def config():
    return PortalConfig(True, "https://vpn.test", "a" * 48, "smtp.test", 465,
                        "test", "test", "login@vpn.test", "notification-secret",
                        1, "help@vpn.test", "https://vpn.test/terms", "https://vpn.test/privacy")


def sign(payload):
    result = {k: v for k, v in payload.items() if k != "sign"}
    result["sign"] = hmac.new(config().notification_secret.encode(), urlencode(sorted(result.items()), quote_via=quote).encode(), hashlib.sha256).hexdigest()
    return result


def notification(order_id, operation="operation-1", amount="150.00"):
    return sign({"notification_type": "card-incoming", "operation_id": operation,
                 "amount": "147.00", "withdraw_amount": amount, "currency": "643",
                 "datetime": "2026-09-28T12:00:00Z", "sender": "", "codepro": "false",
                 "unaccepted": "false", "label": "kw1_" + order_id})


def test_notification_authenticates_gross_amount_and_every_field():
    data = notification("order")
    assert verify_notification(data, config().notification_secret)
    assert paid_amount(data) == 15000
    data["withdraw_amount"] = "1500.00"
    assert not verify_notification(data, config().notification_secret)
    assert not verify_notification(data, "")


def test_notification_uses_rfc3986_encoding_for_spaces_and_plus():
    # Fixed provider-canonical text, independent of the application's encoder.
    canonical = "comment=KYN%20VPN%2B&label=kw1_test"
    payload = {"comment": "KYN VPN+", "label": "kw1_test"}
    payload["sign"] = hmac.new(b"secret", canonical.encode(), hashlib.sha256).hexdigest()
    assert verify_notification(payload, "secret")
    payload["comment"] = "KYN+VPN+"
    assert not verify_notification(payload, "secret")


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "0", "1.001"])
def test_invalid_payment_amount(amount):
    with pytest.raises(ValueError):
        paid_amount(notification("order", amount=amount))


def test_email_and_code_security():
    assert normalize_email("  Person@Example.ru ") == "person@example.ru"
    for value in ["a@b", "a\r\nBcc:x@y.ru", "no email", "a@b.ru\x00"]:
        with pytest.raises(ValueError):
            normalize_email(value)
    assert code_digest("secret", "challenge-a", "123456") != code_digest("secret", "challenge-b", "123456")


async def environment(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.state.portal_config = config()
    app.include_router(router)
    @app.middleware("http")
    async def session_middleware(request, call_next):
        async with factory() as session:
            request.state.session = session
            response = await call_next(request)
            await session.commit()
            return response
    sent = []
    async def fake_mail(cfg, email, code):
        sent.append((email, code))
    async def unlimited(*args):
        pass
    monkeypatch.setattr(services, "send_code", fake_mail)
    monkeypatch.setattr(services, "rate_limit", unlimited)
    monkeypatch.setattr(CONFIG, "month_cost", [150, 450, 900, 1800])
    monkeypatch.setattr(CONFIG, "yoomoney_wallet_token", "41000000000000")
    async with factory() as session:
        session.add(Location(id=1, name="Test"))
        await session.flush()
        session.add(Vds(id=1, name="test", ip="203.0.113.1", max_space=100, location=1))
        await session.flush()
        session.add(Servers(id=1, type_vpn=CONFIG.TypeVpn.VLESS.value, ip="vpn.test:2053", work=True,
                            auto_work=True, inbound_id=1, vds=1, connection_method=True))
        await session.commit()
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://vpn.test", headers={"Origin": "https://vpn.test"})
    return engine, factory, app, client, sent


async def login(client, sent, email="person@example.ru"):
    response = await client.post("/web/api/auth/code", json={"email": email})
    assert response.status_code == 200
    challenge = response.json()["challenge"]
    response = await client.post("/web/api/auth/verify", json={"challenge": challenge, "code": sent[-1][1]})
    assert response.status_code == 200
    return response, challenge


def test_login_replay_csrf_logout_and_expired_session(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        try:
            assert (await client.get("/web/api/account")).status_code == 401
            assert (await client.post("/web/api/auth/code", headers={"Origin": "https://evil.test"}, json={"email": "person@example.ru"})).status_code == 403
            response, challenge = await login(client, sent)
            cookie = response.headers["set-cookie"]
            assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie
            assert (await client.get("/web/api/account")).json()["email"] == "person@example.ru"
            assert (await client.post("/web/api/auth/verify", json={"challenge": challenge, "code": sent[-1][1]})).status_code == 401
            token = client.cookies.get(COOKIE)
            assert (await client.post("/web/api/auth/logout", json={})).status_code == 200
            assert (await client.get("/web/api/account", headers={"Cookie": COOKIE + "=" + token})).status_code == 401
            await login(client, sent)
            async with factory() as session:
                row = await session.scalar(select(WebSession))
                row.expires_at = int(time.time()) - 1
                await session.commit()
            assert (await client.get("/web/api/account")).status_code == 401
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_code_attempt_limit_and_mail_failure(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        try:
            challenge = (await client.post("/web/api/auth/code", json={"email": "person@example.ru"})).json()["challenge"]
            wrong = "000000" if sent[-1][1] != "000000" else "111111"
            for _ in range(5):
                assert (await client.post("/web/api/auth/verify", json={"challenge": challenge, "code": wrong})).status_code == 401
            assert (await client.post("/web/api/auth/verify", json={"challenge": challenge, "code": sent[-1][1]})).status_code == 401
            async def mail_failure(*args):
                raise OSError("smtp unavailable")
            monkeypatch.setattr(services, "send_code", mail_failure)
            response = await client.post("/web/api/auth/code", json={"email": "other@example.ru"})
            assert response.status_code == 503
            async with factory() as session:
                assert await session.scalar(select(WebChallenge).where(WebChallenge.email == "other@example.ru")) is None
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_checkout_payment_idempotency_ownership_and_provision_retry(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        async def panel(session, sub, provision=False):
            if provision:
                sub.provisioned_until = sub.expires_at
                await session.commit()
            return ["vless://test-primary", "vless://test-xhttp"]
        monkeypatch.setattr(services, "panel_access", panel)
        try:
            await login(client, sent)
            assert (await client.post("/web/api/orders", json={"months": 1})).status_code == 422
            response = await client.post("/web/api/orders", json={"months": 1, "accepted_terms": True, "price": 1})
            assert response.status_code == 200
            order_id = response.json()["id"]
            assert "sum=150.00" in response.json()["url"]
            repeat = await client.post("/web/api/orders", json={"months": 1, "accepted_terms": True})
            assert repeat.json()["id"] == order_id
            endpoint = "/web/api/payments/yoomoney"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            payload = notification(order_id)
            probe = sign(dict(payload, test_notification="true"))
            assert (await client.post(endpoint, content=urlencode(probe), headers=headers)).status_code == 200
            assert (await client.get("/web/api/account")).json()["orders"][0]["status"] == "pending"
            assert (await client.get("/web/api/subscription")).status_code == 404
            # The probe flag is signed, and cannot bypass authenticity checks.
            probe["sign"] = "0" * 64
            assert (await client.post(endpoint, content=urlencode(probe), headers=headers)).status_code == 403
            bot_receipt = sign(dict(payload, label="vb2_test"))
            assert (await client.post(endpoint, content=urlencode(bot_receipt), headers=headers)).status_code == 200
            assert (await client.get("/web/api/account")).json()["orders"][0]["status"] == "pending"
            tampered = dict(payload, withdraw_amount="1.00")
            assert (await client.post(endpoint, content=urlencode(tampered), headers=headers)).status_code == 403
            assert (await client.post(endpoint, content=urlencode(notification(order_id, amount="1.00")), headers=headers)).status_code == 400
            assert (await client.get("/web/api/subscription")).status_code == 404
            async def failure(*args, **kwargs):
                raise OSError("panel unavailable")
            monkeypatch.setattr(services, "panel_access", failure)
            response = await client.post(endpoint, content=urlencode(payload), headers=headers)
            assert response.status_code == 503
            state = (await client.get("/web/api/account")).json()
            assert state["orders"][0]["status"] == "paid"
            expiry = state["subscription"]["expires_at"]
            assert not state["subscription"]["ready"]
            monkeypatch.setattr(services, "panel_access", panel)
            assert (await client.post(endpoint, content=urlencode(payload), headers=headers)).status_code == 200
            assert (await client.post(endpoint, content=urlencode(payload), headers=headers)).status_code == 200
            state = (await client.get("/web/api/account")).json()
            assert state["subscription"]["expires_at"] == expiry
            assert state["subscription"]["ready"]
            assert len((await client.get("/web/api/subscription")).json()["links"]) == 2
            assert (await client.get("/web/api/subscription/download")).headers["content-disposition"].startswith("attachment;")
            # A second email cannot see the first user's subscription or orders.
            await client.post("/web/api/auth/logout", json={})
            await login(client, sent, "second@example.ru")
            assert (await client.get("/web/api/account")).json()["subscription"] is None
            assert (await client.get("/web/api/account")).json()["orders"] == []
            assert (await client.get("/web/api/subscription")).status_code == 404
            second = (await client.post("/web/api/orders", json={"months": 1, "accepted_terms": True})).json()["id"]
            assert (await client.post(endpoint, content=urlencode(notification(second)), headers=headers)).status_code == 409
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_checkout_disabled_without_notification_secret(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        try:
            await login(client, sent)
            app.state.portal_config = replace(config(), notification_secret="")
            assert not (await client.get("/web/api/config")).json()["checkout_available"]
            assert (await client.post("/web/api/orders", json={"months": 1, "accepted_terms": True})).status_code == 503
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_panel_provision_preserves_identity_and_verifies_both_inbounds(monkeypatch):
    import json
    calls = []
    inbounds = [
        {"id": i, "port": port, "enable": True, "settings": {"clients": []}, "streamSettings": {
            "network": network, "security": "reality", "xhttpSettings": {"path": "/test", "mode": "auto"},
            "realitySettings": {"serverNames": ["example.com"], "shortIds": ["abcdef"],
                                "settings": {"publicKey": "public-key", "fingerprint": "chrome"}}}}
        for i, port, network in [(1, 443, "tcp"), (2, 2087, "xhttp")]]
    sub = SimpleNamespace(id="subscription", client_uuid="11111111-1111-4111-8111-111111111111",
                          sub_id="sub-id", server_id=1, expires_at=2000000000, quota_bytes=5000, provisioned_until=0)
    server = SimpleNamespace(work=True, type_vpn=CONFIG.TypeVpn.VLESS.value, ip="vpn.test:2053", inbound_id=1,
                             connection_method=True, login="login", password="password")
    class FakePanel:
        def __init__(self, **kwargs):
            pass
        async def login(self, **kwargs):
            pass
        async def close(self):
            pass
        async def request(self, **kwargs):
            calls.append(kwargs)
            if kwargs["method"] == "GET":
                return {"success": True, "obj": inbounds}
            if kwargs["endpoint"].endswith("/add"):
                for inbound in inbounds:
                    inbound["settings"]["clients"] = [dict(kwargs["json"]["client"])]
            if "/update/" in kwargs["endpoint"]:
                for inbound in inbounds:
                    inbound["settings"]["clients"] = [dict(kwargs["json"])]
            return {"success": True}
    class Session:
        async def get(self, *args):
            return server
        async def commit(self):
            pass
    monkeypatch.setattr(services, "CompatXUI", FakePanel)
    monkeypatch.setattr(CONFIG, "xui_fallback_inbound_ids", [2])
    async def scenario():
        links = await services.panel_access(Session(), sub, provision=True)
        assert len(links) == 2 and "2087" in links[1]
        assert sub.provisioned_until == sub.expires_at
        sub.expires_at += 2592000
        await services.panel_access(Session(), sub, provision=True)
        assert sum(c["endpoint"].endswith("/add") for c in calls) == 1
        update = next(c for c in calls if "/update/" in c["endpoint"])
        assert update["json"]["id"] == sub.client_uuid
        assert update["json"]["expiryTime"] == sub.expires_at * 1000
        inbounds[1]["settings"]["clients"] = []
        with pytest.raises(ValueError, match="missing or disabled"):
            await services.panel_access(Session(), sub)
    asyncio.run(scenario())


def test_portal_migration_matches_models():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect
    path = Path(__file__).parents[1] / "bot/bot/alembic/versions/10a2b3c4d5e6_add_web_portal.py"
    spec = importlib.util.spec_from_file_location("portal_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        trial_spec = importlib.util.spec_from_file_location("trial_migration", path.parent / "30c4d5e6f7a8_web_trials.py")
        trial_migration = importlib.util.module_from_spec(trial_spec)
        trial_spec.loader.exec_module(trial_migration)
        trial_migration.op = migration.op
        trial_migration.upgrade()
        invite_spec = importlib.util.spec_from_file_location("invite_migration", path.parent / "40d5e6f7a8b9_web_invites.py")
        invite_migration = importlib.util.module_from_spec(invite_spec)
        invite_spec.loader.exec_module(invite_migration)
        invite_migration.op = migration.op
        invite_migration.upgrade()
        inspector = inspect(connection)
        for table in [WebAccount, WebChallenge, WebSession, WebOrder, WebSubscription, WebTrial]:
            actual = {c["name"] for c in inspector.get_columns(table.__tablename__)}
            assert actual == set(table.__table__.columns.keys())
        invite_migration.downgrade()
        trial_migration.downgrade()
        migration.downgrade()
        assert not inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.skipif(os.getenv("PORTAL_TEST_POSTGRES") != "1", reason="requires isolated localhost:15489/portal_test PostgreSQL")
def test_postgres_migration_and_concurrent_payment_notifications():
    """Real row locks, not SQLite's no-op FOR UPDATE; never use production URL."""
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    async def scenario():
        schema = "portal_test_" + secrets.token_hex(8)
        admin = create_async_engine("postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test")
        engine = create_async_engine("postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test",
                                    connect_args={"server_settings": {"search_path": schema}})
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        try:
            path = Path(__file__).parents[1] / "bot/bot/alembic/versions/10a2b3c4d5e6_add_web_portal.py"
            spec = importlib.util.spec_from_file_location("pg_portal_migration", path)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            invite_spec = importlib.util.spec_from_file_location("pg_invite_migration", path.parent / "40d5e6f7a8b9_web_invites.py")
            invite_migration = importlib.util.module_from_spec(invite_spec)
            invite_spec.loader.exec_module(invite_migration)
            def migrate(connection):
                Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables if not t.name.startswith("web_")])
                migration.op = Operations(MigrationContext.configure(connection))
                migration.upgrade()
                invite_migration.op = migration.op
                invite_migration.upgrade()
            async with engine.begin() as conn:
                await conn.run_sync(migrate)
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                session.add(Location(id=1, name="Test"))
                await session.flush()
                session.add(Vds(id=1, name="test", ip="203.0.113.1", max_space=100, location=1))
                await session.flush()
                session.add(Servers(id=1, type_vpn=CONFIG.TypeVpn.VLESS.value, vds=1, work=True))
                session.add(WebAccount(id="account", email="test@example.ru", created_at=1, disabled=False))
                await session.flush()
                session.add(WebSubscription(id="subscription", account_id="account", server_id=1, client_uuid="uuid", sub_id="sub",
                                            expires_at=2000000000, quota_bytes=0, provisioned_until=2000000000))
                await session.flush()
                session.add(WebOrder(id="order", account_id="account", subscription_id="subscription", months=1,
                                     amount_kopecks=15000, quota_bytes=5000, created_at=1))
                await session.commit()
            async def deliver():
                async with factory() as session:
                    await services.apply_payment(session, "order", "same-operation", 15000)
            await asyncio.gather(*(deliver() for _ in range(4)))
            async with factory() as session:
                sub = await session.get(WebSubscription, "subscription")
                assert sub.expires_at == 2000000000 + int(CONFIG.COUNT_SECOND_MOTH)
                assert sub.quota_bytes == 5000
                assert (await session.get(WebOrder, "order")).operation_id == "same-operation"
            async with engine.begin() as conn:
                def downgrade(connection):
                    migration.op = Operations(MigrationContext.configure(connection))
                    invite_migration.op = migration.op
                    invite_migration.downgrade()
                    migration.downgrade()
                await conn.run_sync(downgrade)
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())


def test_public_plans_visible_but_account_and_checkout_closed_before_launch(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await environment(monkeypatch)
        app.state.portal_config = replace(config(), enabled=False)
        try:
            response = await client.get('/web/api/config')
            assert response.status_code == 200
            data = response.json()
            assert data['plans'] and data['launch_pending']
            assert not data['login_available'] and not data['checkout_available']
            assert (await client.get('/web/api/account')).status_code == 404
            assert (await client.post('/web/api/auth/code', json={'email': 'test@example.ru'})).status_code == 404
            assert not sent
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())
