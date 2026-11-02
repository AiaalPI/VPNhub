import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('render_portal_ingress', ROOT / 'scripts/render_portal_ingress.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_restored_host_uses_new_ipv4_without_stale_ipv6_or_dirty_source(tmp_path):
    template = ROOT / 'configs/portal/nginx-shared.conf'
    original = template.read_text()
    env = tmp_path / 'host.env'
    env.write_text('PORTAL_PUBLIC_IPV4=91.149.255.110\n')
    output = tmp_path / 'runtime/nginx-shared.conf'
    assert module.render(template, env, output) == '91.149.255.110'
    result = output.read_text()
    assert 'listen 91.149.255.110:443;' in result
    assert '89.125.145.65' not in result
    assert '2605:e440:e::3a7' not in result
    assert 'default 127.0.0.1:443;' in result
    assert 'proxy_protocol on;' in result
    assert template.read_text() == original


def test_new_ipv6_listener_is_rendered_and_repeat_is_safe(tmp_path):
    env = tmp_path / 'host.env'
    env.write_text('PORTAL_PUBLIC_IPV4=91.149.255.110\nPORTAL_PUBLIC_IPV6=2605:e440:7::abc\n')
    output = tmp_path / 'nginx-shared.conf'
    for _ in range(2):
        module.render(ROOT / 'configs/portal/nginx-shared.conf', env, output)
    assert 'listen [2605:e440:7::abc]:443;' in output.read_text()


@pytest.mark.parametrize('settings', [
    'PORTAL_PUBLIC_IPV4=0.0.0.0',
    'PORTAL_PUBLIC_IPV4=127.0.0.1',
    'PORTAL_PUBLIC_IPV4=169.254.1.2',
    'PORTAL_PUBLIC_IPV4=91.149.255.110;include /tmp/x;',
    'PORTAL_PUBLIC_IPV4=91.149.255.110\nPORTAL_PUBLIC_IPV6=::',
    'PORTAL_PUBLIC_IPV4=91.149.255.110\nOTHER=value',
    'PORTAL_PUBLIC_IPV4=91.149.255.110\nPORTAL_PUBLIC_IPV4=91.149.255.111',
])
def test_invalid_listener_never_overwrites_existing_config(tmp_path, settings):
    env = tmp_path / 'host.env'
    env.write_text(settings + '\n')
    output = tmp_path / 'nginx-shared.conf'
    output.write_text('last known good')
    with pytest.raises(ValueError):
        module.render(ROOT / 'configs/portal/nginx-shared.conf', env, output)
    assert output.read_text() == 'last known good'
