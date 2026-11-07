import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest

from bot.misc.vpn_public_addresses import parse_public_addresses
from bot.misc.VPN.Xui.Vless import Vless, normalize_vless_export_link
from bot.misc.util import CONFIG
from bot.services.clash_subscription_service import build_clash_config
from bot.services.singbox_subscription_service import build_singbox_config


@pytest.mark.parametrize('value', ['[]', '{"0":"host"}', '{"01":"host"}',
    '{"1":null}', '{"1":"https://host"}', '{"1":"host:443"}',
    '{"1":"user@host"}', '{"1":"host/path"}', '{"1":"bad host"}'])
def test_invalid_endpoint_config_fails_closed(value):
    with pytest.raises(ValueError):
        parse_public_addresses(value)


def test_endpoint_configuration_is_scoped_to_server_id():
    assert parse_public_addresses('') == {}
    assert parse_public_addresses('{"1":"89.125.136.14","2":"2001:db8::1"}') == {
        1: '89.125.136.14', 2: '2001:db8::1'}


def test_constructor_keeps_private_panel_address_and_scopes_override(monkeypatch):
    calls = []
    def panel(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace()
    monkeypatch.setattr('bot.misc.VPN.Xui.XuiBase.CompatXUI', panel)
    monkeypatch.setattr(CONFIG, 'xui_public_addresses', {1: '89.125.136.14'})
    server = SimpleNamespace(id=1, connection_method=True, ip='panel.example.com:2053/private',
        inbound_id=1, login='test', password='test', free_server=False)
    assert Vless(server, 5).public_address == '89.125.136.14'
    server.id = 2
    assert Vless(server, 5).public_address is None
    assert all(call['full_address'] == 'https://panel.example.com:2053/private' for call in calls)


@pytest.mark.parametrize('host', ['89.125.136.14', 'vpn.example.com', '2001:db8::1'])
def test_primary_rewrite_preserves_identity_crypto_port_and_label(host):
    old = ('vless://11111111-1111-4111-8111-111111111111@203.0.113.10:443'
           '?security=reality&type=tcp&pbk=key&sid=abc&sni=example.com'
           '&flow=xtls-rprx-vision#Finland')
    new = urlsplit(normalize_vless_export_link(old, host))
    original = urlsplit(old)
    assert new.hostname == host
    assert new.username == original.username
    assert new.port == original.port
    assert new.fragment == original.fragment
    expected = parse_qs(original.query)
    expected['encryption'] = ['none']
    assert parse_qs(new.query) == expected


def test_export_override_does_not_replace_panel_or_recreate_client(monkeypatch):
    async def scenario():
        monkeypatch.setattr(CONFIG, 'xui_fallback_inbound_ids', [2])
        client = Vless.__new__(Vless)
        client.public_address = '89.125.136.14'
        client.inbound_id = 1
        client.ensure_client = AsyncMock()
        client.get_client = AsyncMock(return_value=SimpleNamespace(id='existing-id'))
        api = SimpleNamespace(
            get_key_vless=AsyncMock(return_value='vless://existing-id@203.0.113.10:443?type=tcp'),
            get_domain=lambda: '203.0.113.10',
            request=AsyncMock(return_value={'obj': {'port': 2087, 'enable': True,
                'streamSettings': {'network': 'xhttp', 'security': 'reality',
                    'xhttpSettings': {'path': '/unchanged', 'mode': 'auto'},
                    'realitySettings': {'serverNames': ['example.com'], 'shortIds': ['abc'],
                        'settings': {'publicKey': 'key'}}}}}),
        )
        client.xui = api
        primary = await client.get_key_user('123.7.vl', 'Finland')
        fallback, = await client.get_fallback_keys('123.7.vl', 'Finland')
        assert client.xui is api
        assert api.get_domain() == '203.0.113.10'
        client.ensure_client.assert_awaited_once_with('123.7.vl', expire_at=None, limit_gb=None)
        api.request.assert_awaited_once_with(method='GET', endpoint='/panel/api/inbounds/get/2')
        assert urlsplit(primary).hostname == urlsplit(fallback).hostname == '89.125.136.14'
        assert urlsplit(fallback).username == 'existing-id'
        assert parse_qs(urlsplit(fallback).query)['path'] == ['/unchanged']
        assert '89.125.136.14' in build_clash_config([primary])
        assert '89.125.136.14' in build_singbox_config([primary])
    asyncio.run(scenario())
