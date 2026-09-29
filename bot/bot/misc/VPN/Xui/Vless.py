import uuid
import json
import time
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

    async def add_client(self, name, limit_ip, limit_gb, expiry_time=0):
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
                            expiryTime=expiry_time,
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

    async def ensure_client(self, name, *, expire_at=None, limit_gb=None):
        """Reconcile absolute settings; retries preserve identity and traffic."""
        ids = list(dict.fromkeys([self.inbound_id, *self.xui.additional_inbound_ids]))

        async def snapshot():
            response = await self.xui.request(method='GET', endpoint='/panel/api/inbounds/list')
            if not isinstance(response, dict) or not response.get('success'):
                raise RuntimeError('Cannot read panel inbounds')
            found = {}
            available = set()
            for inbound in response['obj']:
                if inbound['id'] not in ids:
                    continue
                if inbound.get('enable'):
                    available.add(inbound['id'])
                settings = inbound['settings']
                if isinstance(settings, str):
                    settings = json.loads(settings)
                for item in settings.get('clients', []):
                    if item.get('email') == name:
                        found[inbound['id']] = item
            if available != set(ids):
                raise RuntimeError('A configured VPN inbound is unavailable')
            return found

        found = await snapshot()
        existing = next(iter(found.values()), None)
        # Global lookup also finds clients detached from every configured inbound.
        if existing is None:
            response = await self.xui.request(method='GET', endpoint='/panel/api/clients/list')
            if not isinstance(response, dict) or not response.get('success'):
                raise RuntimeError('Cannot read global panel clients')
            for row in response.get('obj') or []:
                item = row.get('client', row)
                if item.get('email') == name:
                    existing = dict(item)
                    existing['id'] = existing.pop('uuid')
                    for field in ('traffic', 'inboundIds'):
                        existing.pop(field, None)
                    break
        expiry = int(expire_at.timestamp() * 1000) if expire_at is not None else None
        if expiry is not None and expiry <= int(time.time() * 1000):
            raise ValueError('Cannot provision an expired subscription')
        if existing is None:
            limit = limit_gb if limit_gb is not None else (CONFIG.limit_gb_free if self.free_server else CONFIG.limit_GB)
            if not await self.add_client(name, CONFIG.limit_ip, limit, expiry or 0):
                raise RuntimeError('Panel rejected client creation')
        else:
            payload = dict(existing)
            if any(item.get('id') != payload.get('id') for item in found.values()):
                raise RuntimeError('Panel client identity mismatch')
            payload['security'] = payload.get('security') or 'auto'
            payload['tgId'] = int(payload.get('tgId') or 0)
            if expiry is not None:
                # A concurrent stale export must not undo a newer paid renewal.
                expiry = max(expiry, int(payload.get('expiryTime') or 0))
                payload['expiryTime'] = expiry
            if limit_gb is not None:
                payload['totalGB'] = max(int(payload.get('totalGB') or 0), int(limit_gb) * 1073741824)
            # Do not enable a manually disabled client just because someone exports it.
            if expiry is not None:
                payload['enable'] = True
            if payload != existing:
                response = await self.xui.request(method='POST',
                    endpoint='/panel/api/clients/update/' + quote(name, safe=''), json=payload)
                if not response.get('success'):
                    raise RuntimeError('Panel rejected client update')
            missing = sorted(set(ids) - set(found))
            if missing:
                response = await self.xui.request(method='POST',
                    endpoint='/panel/api/clients/' + quote(name, safe='') + '/attach',
                    json={'inboundIds': missing})
                if not response.get('success'):
                    raise RuntimeError('Panel rejected inbound attachment')
        verified = await snapshot()
        if set(verified) != set(ids) or any(
            not item.get('enable') or not item.get('id')
            or (existing is not None and item.get('id') != existing.get('id'))
            or (limit_gb is not None and int(item.get('totalGB', 0)) < int(limit_gb) * 1073741824)
            or (expiry is not None and int(item.get('expiryTime', 0)) != expiry)
            for item in verified.values()
        ):
            raise RuntimeError('Panel client verification failed')
        if len({item['id'] for item in verified.values()}) != 1:
            raise RuntimeError('VPN channels have different client identities')

    async def restore_client_access(self, email, limit_gb=None, expire_at=None):
        await self.ensure_client(email, expire_at=expire_at, limit_gb=limit_gb)
        return 'restored'

    async def get_key_user(self, name, name_key, limit_gb=None, expire_at=None):
        await self.ensure_client(name, expire_at=expire_at, limit_gb=limit_gb)
        link = await self.xui.get_key_vless(
            inbound_id=self.inbound_id, email=name, custom_remark=name_key)
        if not link:
            raise RuntimeError('Panel returned an empty VPN configuration')
        return normalize_vless_export_link(link)

    async def delete_client(self, email):
        response = await self.xui.request(method='POST',
            endpoint='/panel/api/clients/del/' + quote(email, safe=''))
        if not response.get('success'):
            raise RuntimeError('Panel rejected client deletion')
        return True

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
