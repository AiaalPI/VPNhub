import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bot.services import subscription_usage_service as usage_service
from bot.services.subscription_usage_service import SubscriptionUsage, usage_from_global_clients
from bot.webhooks import base


def panel_response(total=50 * 1073741824):
    return {"success": True, "obj": [
        {"email": "other.1.vl", "totalGB": 999, "traffic": {"up": 999, "down": 999}},
        {"email": "123.7.vl", "totalGB": total, "inboundIds": [1, 2],
         "traffic": {"up": 123456789, "down": 987654321}},
    ]}


def test_global_counters_are_exact_and_not_duplicated_per_transport():
    assert usage_from_global_clients(panel_response(), "123.7.vl") == SubscriptionUsage(
        123456789, 987654321, 50 * 1073741824,
    )
    assert usage_from_global_clients(panel_response(total=0), "123.7.vl").total == 0


@pytest.mark.parametrize("invalid", [None, -1, "50", True])
def test_invalid_allowance_never_becomes_unlimited(invalid):
    with pytest.raises(ValueError):
        usage_from_global_clients(panel_response(total=invalid), "123.7.vl")


def test_missing_duplicate_or_incomplete_accounting_is_rejected():
    for response in ({"success": False}, {"success": True, "obj": []},
                     {"success": True, "obj": [{"email": "123.7.vl", "totalGB": 50}]},
                     {"success": True, "obj": [panel_response()["obj"][1]] * 2}):
        with pytest.raises(ValueError):
            usage_from_global_clients(response, "123.7.vl")


def test_reader_checks_ownership_and_closes_failed_panel_session():
    async def scenario():
        key = SimpleNamespace(id=7, user_tgid=123, server=1, server_table=object())
        with patch.object(usage_service, "ServerManager") as factory:
            assert await usage_service.get_subscription_usage(key, 456) is None
            factory.assert_not_called()
        xui = SimpleNamespace(request=AsyncMock(side_effect=TimeoutError()), close=AsyncMock())
        client = SimpleNamespace(xui=xui)
        manager = SimpleNamespace(client=client, login=AsyncMock())
        with patch.object(usage_service, "ServerManager", return_value=manager), \
             patch.object(usage_service, "Vless", SimpleNamespace):
            assert await usage_service.get_subscription_usage(key, 123) is None
        xui.close.assert_awaited_once()
    asyncio.run(scenario())


@pytest.mark.parametrize("suffix", ["", "/clash", "/singbox"])
@pytest.mark.parametrize("usage", [SubscriptionUsage(123, 456, 50 * 1073741824), None])
def test_http_subscription_formats_share_accounting_and_survive_outage(monkeypatch, suffix, usage):
    async def scenario():
        key = SimpleNamespace(id=7, user_tgid=123, subscription=1800000000)
        session = AsyncMock()
        context = AsyncMock()
        context.__aenter__.return_value = session
        monkeypatch.setattr(base.app.state, "session_maker", lambda: context, raising=False)
        monkeypatch.setattr(base.app.state, "bot", object(), raising=False)
        monkeypatch.setattr(base, "parse_clean_subscription_token", lambda token: (123, 7))
        monkeypatch.setattr(base, "get_key_id", AsyncMock(return_value=key))
        monkeypatch.setattr(base, "get_subscription_usage", AsyncMock(return_value=usage))
        monkeypatch.setattr(base, "render_clean_subscription_payload", AsyncMock(return_value="vless://test"))
        monkeypatch.setattr(base, "get_clean_marzban_links", AsyncMock(return_value=["vless://test"]))
        monkeypatch.setattr(base, "build_clash_config", lambda links: "proxies: []")
        monkeypatch.setattr(base, "build_singbox_config", lambda links: '{"outbounds": []}')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app), base_url="https://test") as client:
            response = await client.get("/subscriptions/test-token" + suffix)
        assert response.status_code == 200
        if usage is None:
            assert "subscription-userinfo" not in response.headers
        else:
            assert response.headers["subscription-userinfo"] == (
                "upload=123; download=456; total=53687091200; expire=1800000000"
            )
        assert response.headers["cache-control"] == "no-store"
    asyncio.run(scenario())
