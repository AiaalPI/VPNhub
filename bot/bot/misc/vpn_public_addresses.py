"""Validated export-only addresses; panel API endpoints are never rewritten."""
import ipaddress
import json
import re


def parse_public_addresses(value: str) -> dict[int, str]:
    if not value.strip():
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError('XUI_PUBLIC_ADDRESSES must be a JSON object')
    result = {}
    for key, address in data.items():
        if not key.isdecimal() or int(key) <= 0 or str(int(key)) != key:
            raise ValueError('Public address keys must be canonical positive server IDs')
        if not isinstance(address, str) or not address:
            raise ValueError('Public address must be an IP address or DNS hostname')
        try:
            address = str(ipaddress.ip_address(address))
        except ValueError:
            if len(address) > 253 or not all(
                re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
                for label in address.split('.')
            ):
                raise ValueError('Public address cannot include scheme, port, path or credentials')
        result[int(key)] = address
    return result
