import asyncio
import time
from types import SimpleNamespace

import pytest
from aiogram.utils.deep_linking import decode_payload
from sqlalchemy import select

from bot.database.models.main import Persons
from bot.database.methods.get import get_count_referral_user
from bot.portal import invitations
from bot.portal.models import WebAccount
from test_web_portal import config, environment, login


async def invited_environment(monkeypatch):
    engine, factory, app, client, sent = await environment(monkeypatch)
    class FakeBot:
        async def me(self):
            return SimpleNamespace(username="test_invite_bot")
    @app.middleware("http")
    async def bot_middleware(request, call_next):
        request.state.bot = FakeBot()
        return await call_next(request)
    async with factory() as session:
        session.add_all([Persons(tgid=123, blocked=False, banned=True),
                         Persons(tgid=456, blocked=False, banned=False)])
        await session.commit()
    return engine, factory, app, client, sent


def test_invite_signatures_reject_tampering_and_expiry():
    token = invitations.sign("secret", 123, int(time.time()) + 30)
    assert invitations.read("secret", token) == 123
    assert invitations.read("other", token) is None
    assert invitations.read("secret", token.replace("123.", "456.")) is None
    assert invitations.read("secret", invitations.sign("secret", 123, 1)) is None
    for bad in ["x", "1.2.3", "x" * 200, "123.9.🥷", "-1.9999999999.a"]:
        assert invitations.read("secret", bad) is None


def test_invitation_routes_preserve_referrer_on_both_choices(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await invited_environment(monkeypatch)
        try:
            generic = await client.get("/web/invite")
            assert generic.status_code == 200
            assert 'href="/web/#email"' in generic.text
            assert 'href="/web/go/telegram"' in generic.text
            assert "Для Telegram может понадобиться VPN." in generic.text
            assert (await client.get("/web/go/telegram")).headers["location"].startswith("https://t.me/test_invite_bot")
            for invalid in [0, -1, 999, 9223372036854775808]:
                assert (await client.get(f"/web/invite/{invalid}")).status_code == 404
            response = await client.get("/web/invite/123")
            assert response.status_code == 200
            cookie = response.headers["set-cookie"]
            assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
            assert 'href="/web/go/telegram/123"' in response.text
            assert 'href="/web/go/telegram/123"' in (await client.get("/web/invite/456")).text
            redirect = await client.get("/web/go/telegram/123")
            assert redirect.status_code == 302
            assert redirect.headers["location"].startswith("https://t.me/test_invite_bot?start=")
            assert decode_payload(redirect.headers["location"].split("start=")[1]) == "123"
            await login(client, sent)
            async with factory() as session:
                account = await session.scalar(select(WebAccount))
                assert account.referral_tgid == 123
                assert await get_count_referral_user(session, 123) == 1
            assert not client.cookies.get(invitations.COOKIE)
            # Later links and logins cannot rewrite existing attribution.
            await client.get("/web/invite/456")
            await login(client, sent)
            async with factory() as session:
                assert (await session.scalar(select(WebAccount))).referral_tgid == 123
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_bot_issues_website_invitation_when_portal_is_enabled(monkeypatch):
    from bot.handlers.user.referral_user import get_referral_link, _ref_text
    monkeypatch.setenv("PORTAL_ENABLED", "true")
    monkeypatch.setenv("PORTAL_ORIGIN", "https://vpn.test")
    monkeypatch.setenv("PORTAL_SECRET", "a" * 48)
    link = asyncio.run(get_referral_link(SimpleNamespace(), 123))
    assert link == "https://vpn.test/web/invite/123"
    for lang in ["ru", "en"]:
        caption = _ref_text(lang, link, 2, 1, 3)
        assert "Telegram" in caption and link in caption
        assert "referral_program_text" not in caption


@pytest.mark.parametrize("cookie_mode", ["tampered", "changed_after_code", "blocked_after_code"])
def test_referral_captured_at_code_issuance_and_validated(monkeypatch, cookie_mode):
    async def scenario():
        engine, factory, app, client, sent = await invited_environment(monkeypatch)
        try:
            await client.get("/web/invite/123")
            if cookie_mode == "tampered":
                client.cookies.clear()
                client.cookies.set(invitations.COOKIE, invitations.sign("wrong", 456, int(time.time()) + 60))
            response = await client.post("/web/api/auth/code", json={"email": "new@example.ru"})
            assert response.status_code == 200
            if cookie_mode == "changed_after_code":
                client.cookies.clear()
                client.cookies.set(invitations.COOKIE, invitations.sign(config().secret, 456, int(time.time()) + 60))
            if cookie_mode == "blocked_after_code":
                async with factory() as session:
                    person = await session.scalar(select(Persons).where(Persons.tgid == 123))
                    person.blocked = True
                    await session.commit()
            assert (await client.post("/web/api/auth/verify", json={"challenge": response.json()["challenge"], "code": sent[-1][1]})).status_code == 200
            async with factory() as session:
                account = await session.scalar(select(WebAccount))
                assert account.referral_tgid == (123 if cookie_mode == "changed_after_code" else None)
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())


def test_existing_unattributed_account_and_telegram_failure(monkeypatch):
    async def scenario():
        engine, factory, app, client, sent = await invited_environment(monkeypatch)
        async def unavailable(*args, **kwargs):
            raise TimeoutError()
        try:
            await login(client, sent)
            await client.get("/web/invite/123")
            await login(client, sent)
            async with factory() as session:
                assert (await session.scalar(select(WebAccount))).referral_tgid is None
            monkeypatch.setattr("bot.portal.routes.create_start_link", unavailable)
            assert (await client.get("/web/invite/123")).status_code == 200
            result = await client.get("/web/go/telegram/123")
            assert result.status_code == 503 and 'href="/web/#email"' in result.text
        finally:
            await client.aclose()
            await engine.dispose()
    asyncio.run(scenario())
