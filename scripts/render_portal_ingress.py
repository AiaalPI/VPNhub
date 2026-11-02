#!/usr/bin/env python3
"""Render per-host ingress addresses without modifying the tracked config."""
import argparse
import ipaddress
import os
from pathlib import Path
import tempfile


def render(template: Path, environment: Path, output: Path) -> str:
    values = {}
    for line in environment.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        if not separator or name not in {'PORTAL_PUBLIC_IPV4', 'PORTAL_PUBLIC_IPV6'} or name in values:
            raise ValueError('Expected unique PORTAL_PUBLIC_IPV4/PORTAL_PUBLIC_IPV6 assignments')
        values[name] = value.strip()
    if not values.get('PORTAL_PUBLIC_IPV4'):
        raise ValueError('PORTAL_PUBLIC_IPV4 is required')
    ipv4 = ipaddress.IPv4Address(values['PORTAL_PUBLIC_IPV4'])
    ipv6 = ipaddress.IPv6Address(values['PORTAL_PUBLIC_IPV6']) if values.get('PORTAL_PUBLIC_IPV6') else None
    for address in (ipv4, ipv6):
        if address and (address.is_unspecified or address.is_loopback or address.is_multicast or address.is_link_local):
            raise ValueError('Ingress requires an explicit non-loopback host address')
    source = template.read_text()
    old4 = '        listen 89.125.145.65:443;'
    old6 = '        listen [2605:e440:e::3a7]:443;'
    if source.count(old4) != 1 or source.count(old6) != 1:
        raise ValueError('Unexpected ingress listener template')
    text = source.replace(old4, f'        listen {ipv4}:443;')
    text = text.replace(old6 + '\n', f'        listen [{ipv6}]:443;\n' if ipv6 else '')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=output.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(text)
        temporary.chmod(0o644)
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return str(ipv4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--env', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(render(args.template, args.env, args.output))
