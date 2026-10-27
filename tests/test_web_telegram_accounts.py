"""Account ownership, both confirmations and live cross-channel entitlements."""
import asyncio
import os
import secrets
import time
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from bot.database.models.main import Keys, Payments, Persons
from bot.portal import accounts, services
from bot.portal.models import WebAccount, WebSubscription, WebTelegramChallenge, WebTelegramLink
from test_web_portal import environment, login


async def linked_environment(monkeypatch):
    values = await environment(monkeypatch)
    engine, factory, app, client, sent = values
    class FakeBot:
        async def me(self):
            return SimpleNamespace(username="test_link_bot")
    @app.middleware("http")
    async def bot_middleware(request, call_next):
        request.state.bot = FakeBot()
        return await call_next(request)
    monkeypatch.setenv("PORTAL_ENABLED", "true")
    monkeypatch.setenv("PORTAL_ORIGIN", "https://vpn.test")
    monkeypatch.setenv("PORTAL_SECRET", "a" * 48)
    return values


async def begin(client):
    result = await client.post("/web/api/telegram/link", json={})
    assert result.status_code == 200, result.text
    data = result.json()
    payload = parse_qs(urlsplit(data["url"]).query)["start"][0]
    assert payload.startswith(accounts.LINK_PREFIX) and len(payload) <= 64
    return data["request_id"], payload[len(accounts.LINK_PREFIX):]


async def claim(factory, token, tgid=123, *, approve=True):
    async with factory() as session:
        await accounts.claim_link(session, token, SimpleNamespace(
            id=tgid, full_name="Test User", username="test_user", language_code="ru"))
        if approve:
            await accounts.approve_link(session, token, tgid)


def test_both_confirmations_csrf_session_isolation_and_replay(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await linked_environment(monkeypatch)
        try:
            assert (await client.post("/web/api/telegram/link", json={})).status_code == 401
            await login(client, sent)
            assert (await client.post("/web/api/telegram/link", json={}, headers={"Origin": "https://evil.test"})).status_code == 403
            request_id, token = await begin(client)
            async with factory() as session:
                row = await session.scalar(select(WebTelegramChallenge))
                assert token not in row.digest and row.digest == request_id
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 409
            await claim(factory, token, approve=False)
            # Merely opening an attacker's /start link cannot authorize access.
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 409
            async with factory() as session:
                with pytest.raises(HTTPException):
                    await accounts.approve_link(session, token, 456)
                await accounts.approve_link(session, token, 123)
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(WebTelegramLink)) == 0
            state = (await client.get("/web/api/account")).json()["telegram"]
            assert state["candidate"]["telegram_id"] == 123 and not state["linked"]
            with pytest.raises(HTTPException):
                await claim(factory, token, 456)
            # Another authenticated email cannot consume this confirmation.
            await client.post("/web/api/auth/logout", json={})
            await login(client, sent, "other@example.ru")
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 409
            assert (await client.get("/web/api/account")).json()["telegram_subscriptions"] == []
            await client.post("/web/api/auth/logout", json={})
            await login(client, sent)
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).json()["linked"]
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 409
            assert (await client.post("/web/api/telegram/link", json={})).status_code == 409
            with pytest.raises(HTTPException):
                await claim(factory, token)
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(Keys)) == 0
                assert await session.scalar(select(func.count()).select_from(WebSubscription)) == 0
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_old_expired_and_blocked_candidates_never_link(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await linked_environment(monkeypatch)
        try:
            await login(client, sent)
            _, old_token = await begin(client)
            request_id, token = await begin(client)
            with pytest.raises(HTTPException):
                await claim(factory, old_token)
            async with factory() as session:
                row = await session.get(WebTelegramChallenge, request_id)
                row.expires_at = 1
                await session.commit()
            with pytest.raises(HTTPException):
                await claim(factory, token)
            request_id, token = await begin(client)
            await claim(factory, token)
            async with factory() as session:
                session.add(Persons(tgid=123, blocked=True))
                await session.commit()
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 403
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(WebTelegramLink)) == 0
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_subscriptions_history_and_renewals_use_live_records(monkeypatch):
    async def scenario():
        from bot.handlers.account import active_web_subscription
        engine, factory, app, client, sent = await linked_environment(monkeypatch)
        try:
            await login(client, sent)
            request_id, token = await begin(client)
            await claim(factory, token)
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 200
            expiry = int(time.time()) + 86400
            async with factory() as session:
                user = await session.scalar(select(WebAccount))
                person = await session.scalar(select(Persons).where(Persons.tgid == 123))
                session.add(Persons(tgid=999))
                await session.flush()
                session.add(Keys(id=42, user_tgid=123, subscription=expiry, server=1, paid_quota_gb=50))
                session.add(Keys(id=43, user_tgid=999, subscription=expiry, server=1))
                session.add(WebSubscription(id="web-sub", account_id=user.id, server_id=1, client_uuid="same-uuid",
                    sub_id="same-sub-id", expires_at=expiry, quota_bytes=500, provisioned_until=expiry))
                session.add(Payments(user=person.id, amount=99, data=datetime.now(), status="paid", month_count=1))
                await session.commit()
            state = (await client.get("/web/api/account")).json()
            assert [s["id"] for s in state["telegram_subscriptions"]] == [42]
            assert state["history"][0]["amount_kopecks"] == 9900
            assert not state["trial"]["eligible"]
            assert (await client.post("/web/api/trial", json={})).status_code == 409
            assert (await client.get("/web/api/telegram/subscriptions/43/profiles")).status_code == 404
            async with factory() as session:
                key = await session.get(Keys, 42)
                key.subscription += 86400
                await session.commit()
                assert (await active_web_subscription(session, 123)).client_uuid == "same-uuid"
                assert await accounts.web_access_used(session, 123)
            assert (await client.get("/web/api/account")).json()["telegram_subscriptions"][0]["expires_at"] == expiry + 86400
            # Identity linking never copies/renames an existing panel identity.
            async with factory() as session:
                sub = await session.get(WebSubscription, "web-sub")
                assert sub.client_uuid == "same-uuid" and sub.sub_id == "same-sub-id"
                assert await session.scalar(select(func.count()).select_from(WebSubscription)) == 1
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_start_tokens_are_redacted_in_both_logging_paths():
    from aiogram.types import CallbackQuery, Chat, Message, User
    from bot.middlewares.conversion_events import _message_event
    from bot.middlewares.update_logging import _event_payload
    token = "A" * 43
    message = Message(message_id=1, date=datetime.now(), chat=Chat(id=1, type="private"), text="/start web_" + token)
    assert token not in _event_payload(message)
    assert token not in _message_event(message)[1]
    assert _event_payload(message.model_copy(update={"text": "   "})) == "   "
    callback = CallbackQuery(id="callback", from_user=User(id=123, is_bot=False, first_name="Test"),
        chat_instance="chat", message=message, data="pl_yes:" + token)
    assert token not in _event_payload(callback)


def test_telegram_can_cancel_before_website_confirmation(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await linked_environment(monkeypatch)
        try:
            await login(client, sent)
            request_id, token = await begin(client)
            await claim(factory, token, approve=False)
            async with factory() as session:
                await accounts.approve_link(session, token, 123, cancel=True)
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 409
            state = (await client.get("/web/api/account")).json()
            assert not state["telegram"]["linked"] and not state["telegram"]["pending"]
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_telegram_profiles_are_read_only_and_website_renewal_is_visible_in_bot(monkeypatch):
    async def scenario():
        from unittest.mock import AsyncMock
        from bot.handlers.account import active_web_subscription, show_account
        engine, factory, app, client, sent = await linked_environment(monkeypatch)
        calls = []
        class Panel:
            def __init__(self, **kwargs):
                pass
            async def login(self, **kwargs):
                pass
            async def close(self):
                pass
            async def request(self, **kwargs):
                calls.append(kwargs)
                assert kwargs["method"] == "GET"
                return {"success": True, "obj": [{"id": i, "port": port, "enable": True,
                    "settings": {"clients": [{"email": "123.42.vl", "id": "same-client", "enable": True}]},
                    "streamSettings": {"network": network, "security": "reality",
                        "xhttpSettings": {"path": "/test", "mode": "auto"},
                        "realitySettings": {"serverNames": ["example.com"], "shortIds": ["abcd"],
                            "settings": {"publicKey": "public", "fingerprint": "chrome"}}}}
                    for i, port, network in [(1, 443, "tcp"), (2, 2087, "xhttp")]]}
        monkeypatch.setattr(services, "CompatXUI", Panel)
        monkeypatch.setattr(services.CONFIG, "xui_fallback_inbound_ids", [2])
        try:
            await login(client, sent)
            request_id, token = await begin(client)
            await claim(factory, token)
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 200
            async with factory() as session:
                session.add(Keys(id=42, user_tgid=123, subscription=int(time.time()) + 86400, server=1))
                await session.commit()
            response = await client.get("/web/api/telegram/subscriptions/42/profiles")
            assert response.status_code == 200, response.text
            assert len(response.json()["links"]) == 2 and len(calls) == 1
            # A website order grants time to one existing record, immediately
            # readable by the bot; no second key or synchronization job.
            response = await client.post("/web/api/orders", json={"months": 1, "accepted_terms": True})
            assert response.status_code == 200
            async with factory() as session:
                await services.apply_payment(session, response.json()["id"], "verified-test-payment", 15000)
                sub = await active_web_subscription(session, 123)
                assert sub.expires_at > time.time()
                message = SimpleNamespace(answer=AsyncMock())
                await show_account(message, session, 123, "ru")
                text = message.answer.call_args.args[0]
                assert "portal_" not in text and "Подписка сайта" in text
                assert "№42" in text
                assert await session.scalar(select(func.count()).select_from(Keys)) == 1
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_new_link_cannot_replace_an_existing_telegram_owner(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await linked_environment(monkeypatch)
        try:
            await login(client, sent)
            request_id, token = await begin(client)
            await claim(factory, token)
            assert (await client.post("/web/api/telegram/confirm", json={"request_id": request_id})).status_code == 200
            await client.post("/web/api/auth/logout", json={})
            await login(client, sent, "second@example.ru")
            _, token = await begin(client)
            with pytest.raises(HTTPException) as error:
                await claim(factory, token)
            assert error.value.status_code == 409
            assert not (await client.get("/web/api/account")).json()["telegram"]["linked"]
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


@pytest.mark.skipif(os.getenv("PORTAL_TEST_POSTGRES") != "1", reason="isolated PostgreSQL required")
def test_postgres_migration_and_competing_confirmations():
    """Use a random local-only schema, real FK constraints and row locks."""
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from bot.database.models.main import Base
    async def scenario():
        schema = "identity_test_" + secrets.token_hex(8)
        url = "postgresql+asyncpg://postgres@127.0.0.1:15489/portal_test"
        admin = create_async_engine(url)
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        path = Path(__file__).parents[1] / "bot/bot/alembic/versions/50e6f7a8b9c0_link_web_telegram.py"
        spec = importlib.util.spec_from_file_location("identity_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        def migrate(connection):
            Base.metadata.create_all(connection, tables=[t for t in Base.metadata.sorted_tables
                if t.name not in {"web_telegram_links", "web_telegram_challenges"}])
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(migrate)
            async with factory() as session:
                session.add_all([WebAccount(id="a", email="a@example.test", created_at=1, disabled=False),
                    WebAccount(id="b", email="b@example.test", created_at=1, disabled=False),
                    Persons(tgid=123, blocked=False)])
                await session.commit()
                token_a, request_a = await accounts.begin_link(session, "a")
                token_b, request_b = await accounts.begin_link(session, "b")
            await claim(factory, token_a)
            await claim(factory, token_b)
            async def confirm(account_id, request_id):
                async with factory() as session:
                    try:
                        await accounts.confirm_link(session, account_id, request_id)
                        return 200
                    except HTTPException as error:
                        return error.status_code
            assert sorted(await asyncio.gather(confirm("a", request_a), confirm("b", request_b))) == [200, 409]
            async with factory() as session:
                assert await session.scalar(select(func.count()).select_from(WebTelegramLink)) == 1
                # Removing a Telegram identity revokes its link, preserving web data.
                person = await session.scalar(select(Persons).where(Persons.tgid == 123))
                await session.delete(person)
                await session.commit()
                assert await session.scalar(select(func.count()).select_from(WebTelegramLink)) == 0
                assert await session.scalar(select(func.count()).select_from(WebAccount)) == 2
            async with engine.begin() as conn:
                await conn.run_sync(lambda c: setattr(migration, "op", Operations(MigrationContext.configure(c))))
                await conn.run_sync(lambda c: migration.downgrade())
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            await admin.dispose()
    asyncio.run(scenario())
