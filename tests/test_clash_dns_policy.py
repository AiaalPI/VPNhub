import yaml
from bot.services.clash_subscription_service import build_clash_config


def test_export_dns_uses_google_and_quad9_without_cloudflare():
    config = build_clash_config(['vless://11111111-1111-4111-8111-111111111111@192.0.2.1:443?type=tcp&security=reality&sni=example.com&pbk=public&sid=abcd&fp=chrome#VPN'])
    parsed = yaml.safe_load(config)
    assert parsed['dns']['nameserver'] == ['8.8.8.8', '9.9.9.9']
    assert parsed['dns']['fallback'] == ['tls://8.8.8.8', 'tls://9.9.9.9']
    assert 'cloudflare' not in config.lower()
    assert '1.1.1.1' not in config and '1.0.0.1' not in config
