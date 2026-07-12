import uuid
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import pyxui_async.errors
from pyxui_async import ClientSettings, Client

from bot.misc.VPN.Xui.XuiBase import XuiBase
from bot.misc.util import CONFIG


def normalize_vless_export_link(link: str) -> str:
    parts = urlsplit(link)
    if parts.scheme != 'vless':
        return link
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault('encryption', 'none')
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query, doseq=True),
            parts.fragment,
        )
    )


def build_vless_xhttp_link(
    *,
    client_id: str,
    address: str,
    inbound: dict[str, Any],
    remark: str,
) -> str:
    stream = inbound.get('streamSettings') or {}
    if isinstance(stream, str):
        import json

        stream = json.loads(stream)
    if stream.get('network') != 'xhttp' or stream.get('security') != 'reality':
        raise ValueError('fallback inbound is not XHTTP/REALITY')

    reality = stream.get('realitySettings') or {}
    client_reality = reality.get('settings') or {}
    xhttp = stream.get('xhttpSettings') or {}
    server_names = reality.get('serverNames') or []
    short_ids = reality.get('shortIds') or []
    server_name = client_reality.get('serverName') or (server_names[0] if server_names else '')
    short_id = short_ids[0] if short_ids else ''
    public_key = client_reality.get('publicKey') or client_reality.get('password') or ''
    if not all((client_id, address, inbound.get('port'), server_name, short_id, public_key)):
        raise ValueError('incomplete XHTTP/REALITY export settings')

    query = {
        'type': 'xhttp',
        'security': 'reality',
        'encryption': 'none',
        'path': xhttp.get('path', '/'),
        'mode': xhttp.get('mode', 'auto'),
        'fp': client_reality.get('fingerprint') or 'chrome',
        'sni': server_name,
        'pbk': public_key,
        'sid': short_id,
        'spx': client_reality.get('spiderX') or '/',
    }
    if xhttp.get('host'):
        query['host'] = xhttp['host']
    host = f'[{address}]' if ':' in address and not address.startswith('[') else address
    return urlunsplit(
        (
            'vless',
            f'{client_id}@{host}:{int(inbound["port"])}',
            '',
            urlencode(query),
            quote(remark, safe=''),
        )
    )


class Vless(XuiBase):
    NAME_VPN = 'Vless 🐊'
    POST_FIX = 'vl'

    def __init__(self, server, timeout):
        super().__init__(server, timeout)
        self.xui.additional_inbound_ids = CONFIG.xui_fallback_inbound_ids

    async def add_client(self, name, limit_ip, limit_gb):
        try:
            try:
                new_id = await self.xui.get_new_uuid()
                new_id = new_id.obj.uuid
            except Exception as e:
                new_id = str(uuid.uuid4())
            flow = await self.get_flow()
            response = await self.xui.add_clients(
                inbound_id=self.inbound_id,
                client_settings=ClientSettings(
                    clients=[
                        Client(
                            id=new_id,
                            email=str(name),
                            limitIp=limit_ip,
                            totalGB=limit_gb * 1073741824,
                            flow=flow,
                            subId=self.random_lower_and_num(16)
                        )
                    ]
                )
            )
            if response.success:
                return True
            return False
        except pyxui_async.errors.NotFound:
            return False

    async def get_flow(self):
        inbound = await self.get_inbound()
        if inbound is None:
            return ''
        if inbound.obj.protocol != 'vless':
            return ''
        if inbound.obj.streamSettings.network != 'tcp':
            return ''
        if inbound.obj.streamSettings.security != "reality":
            return ''
        return 'xtls-rprx-vision'

    async def get_key_user(self, name, name_key, limit_gb: int | None = None):
        client = await self.get_client(name)
        if client is None:
            resolved_limit_gb = int(limit_gb) if limit_gb is not None else None
            if self.free_server:
                await self.add_client(
                    name, CONFIG.limit_ip, resolved_limit_gb or CONFIG.limit_gb_free
                )
            else:
                await self.add_client(
                    name, CONFIG.limit_ip, resolved_limit_gb or CONFIG.limit_GB
                )
        link = await self.xui.get_key_vless(
            inbound_id=self.inbound_id,
            email=name,
            custom_remark=name_key
        )
        return normalize_vless_export_link(link)

    async def get_fallback_keys(self, name: str, name_key: str) -> list[str]:
        client = await self.get_client(name)
        if client is None or not getattr(client, 'id', None):
            return []

        links = []
        for inbound_id in CONFIG.xui_fallback_inbound_ids:
            if int(inbound_id) == self.inbound_id:
                continue
            result = await self.xui.request(
                method='GET',
                endpoint=f'/panel/api/inbounds/get/{int(inbound_id)}',
            )
            inbound = result.get('obj') if isinstance(result, dict) else None
            if not inbound or not inbound.get('enable'):
                continue
            links.append(
                build_vless_xhttp_link(
                    client_id=client.id,
                    address=self.xui.get_domain(),
                    inbound=inbound,
                    remark=f'{name_key} | MTS XHTTP',
                )
            )
        return links
