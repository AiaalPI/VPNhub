import asyncio
from urllib.parse import parse_qs, urlsplit

from pyxui_async import Client, ClientSettings

from bot.misc.VPN.Xui.CompatXUI import CompatXUI
from bot.misc.VPN.Xui.Vless import build_vless_xhttp_link
from bot.services.clash_subscription_service import build_clash_config
from bot.services.singbox_subscription_service import build_singbox_config


def _xhttp_link() -> str:
    return build_vless_xhttp_link(
        client_id="11111111-1111-4111-8111-111111111111",
        address="203.0.113.10",
        inbound={
            "port": 2087,
            "streamSettings": {
                "network": "xhttp",
                "security": "reality",
                "xhttpSettings": {"path": "/mobile", "mode": "auto"},
                "realitySettings": {
                    "serverNames": ["example.com"],
                    "shortIds": ["0123456789abcdef"],
                    "settings": {
                        "publicKey": "public-key",
                        "fingerprint": "chrome",
                        "spiderX": "/",
                    },
                },
            },
        },
        remark="VPNHub | MTS XHTTP",
    )


def test_build_vless_xhttp_link_contains_required_parameters():
    parts = urlsplit(_xhttp_link())
    query = parse_qs(parts.query)

    assert parts.scheme == "vless"
    assert parts.hostname == "203.0.113.10"
    assert parts.port == 2087
    assert query["type"] == ["xhttp"]
    assert query["security"] == ["reality"]
    assert query["encryption"] == ["none"]
    assert query["path"] == ["/mobile"]
    assert query["mode"] == ["auto"]
    assert query["sni"] == ["example.com"]
    assert query["pbk"] == ["public-key"]
    assert query["sid"] == ["0123456789abcdef"]
    assert "flow" not in query


def test_generated_clash_and_singbox_configs_skip_xhttp_fallback():
    primary = (
        "vless://11111111-1111-4111-8111-111111111111@203.0.113.10:443"
        "?type=tcp&security=reality&encryption=none&sni=example.com"
        "&pbk=public-key&sid=0123456789abcdef#Primary"
    )

    assert "2087" not in build_clash_config([primary, _xhttp_link()])
    assert "2087" not in build_singbox_config([primary, _xhttp_link()])


def test_compat_xui_adds_new_client_to_primary_and_fallback_inbounds():
    xui = CompatXUI(
        full_address="https://127.0.0.1:2053",
        panel="sanaei",
        https=True,
    )
    xui.additional_inbound_ids = [2]
    captured = {}

    async def fake_request(**kwargs):
        captured.update(kwargs)
        return {"success": True, "msg": "ok"}

    xui.request = fake_request
    response = asyncio.run(
        xui.add_clients(
            inbound_id=1,
            client_settings=ClientSettings(
                clients=[
                    Client(
                        id="11111111-1111-4111-8111-111111111111",
                        email="123.456.vl",
                        flow="xtls-rprx-vision",
                        totalGB=107374182400,
                    )
                ]
            ),
        )
    )

    assert response.success is True
    assert captured["endpoint"] == "/panel/api/clients/add"
    assert captured["json"]["inboundIds"] == [1, 2]
    assert captured["json"]["client"]["email"] == "123.456.vl"
