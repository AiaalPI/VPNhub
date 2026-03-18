import datetime
import logging

import httpx

from bot.database.models.main import Servers
from bot.misc.VPN.BaseVpn import BaseVpn
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)


class Marzban(BaseVpn):
    NAME_VPN = 'Marzban'
    POST_FIX = 'mz'
    DEFAULT_INBOUND_TAG = 'VLESS_REALITY'

    def __init__(self, server: Servers, timeout=30):
        self.free_server = server.free_server
        self.timeout = timeout
        self.base_url = server.panel.rstrip('/')
        self.username = server.login
        self.password = server.password
        self.token: str | None = None
        self.client: httpx.AsyncClient | None = None
        self.inbound_tag: str = self.DEFAULT_INBOUND_TAG

    async def login(self):
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=False
        ) as tmp:
            resp = await tmp.post(
                '/api/admin/token',
                data={
                    'username': self.username,
                    'password': self.password,
                    'grant_type': 'password',
                }
            )
            resp.raise_for_status()
            self.token = resp.json()['access_token']

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={'Authorization': f'Bearer {self.token}'},
            timeout=self.timeout,
            verify=False
        )

    def _make_username(self, name: str) -> str:
        return name.replace('.', '_')

    @staticmethod
    def _is_vision_flow(user_payload: dict) -> bool:
        try:
            flow_value = (
                (user_payload.get('proxies') or {})
                .get('vless', {})
                .get('flow')
            )
            return str(flow_value or '').strip() == 'xtls-rprx-vision'
        except Exception:
            return False

    async def _ensure_compatible_vless_flow(self, name: str, user_payload: dict) -> dict:
        """
        Force VLESS flow compatibility for broader client support.

        Some clients (notably Android/Hiddify without full xray-core feature set)
        can fail on `xtls-rprx-vision`. We normalize flow to empty string.
        """
        if not self._is_vision_flow(user_payload):
            return user_payload
        username = self._make_username(name)
        try:
            resp = await self.client.put(
                f'/api/user/{username}',
                json={'proxies': {'vless': {'flow': ''}}},
            )
            resp.raise_for_status()
            updated = resp.json()
            log.info(
                'event=marzban.flow_compat user=%s from=xtls-rprx-vision to=empty',
                username
            )
            return updated
        except Exception:
            log.exception(
                'event=marzban.flow_compat_failed user=%s',
                username
            )
            return user_payload

    async def get_all_user_server(self) -> list[dict]:
        if self.client is None:
            return []
        offset = 0
        limit = 100
        users = []
        try:
            while True:
                resp = await self.client.get(
                    '/api/users',
                    params={'offset': offset, 'limit': limit}
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get('users', [])
                users.extend(batch)
                if len(batch) < limit:
                    break
                offset += limit
        except Exception as e:
            log.error('Error get Marzban users list', exc_info=e)
            return []
        return users

    async def get_client(self, name: str) -> dict:
        username = self._make_username(name)
        resp = await self.client.get(f'/api/user/{username}')
        resp.raise_for_status()
        return resp.json()

    async def get_nodes(self) -> list[dict]:
        resp = await self.client.get('/api/nodes')
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            nodes = payload.get('nodes')
            if isinstance(nodes, list):
                return nodes
        return []

    async def _resolve_inbound_tag(self) -> str:
        """
        Resolve the active VLESS inbound tag from Marzban itself.

        This makes provisioning resilient when the panel tag differs from the
        legacy hardcoded default.
        """
        try:
            resp = await self.client.get('/api/inbounds')
            resp.raise_for_status()
            payload = resp.json() or {}
            vless_inbounds = payload.get('vless') or []
            if isinstance(vless_inbounds, list) and vless_inbounds:
                for inbound in vless_inbounds:
                    tag = str(inbound.get('tag') or '').strip()
                    if tag == self.DEFAULT_INBOUND_TAG:
                        self.inbound_tag = tag
                        return tag
                first_tag = str(vless_inbounds[0].get('tag') or '').strip()
                if first_tag:
                    self.inbound_tag = first_tag
                    return first_tag
        except Exception:
            log.exception('event=marzban.resolve_inbound_tag_failed')
        return self.inbound_tag

    async def get_client_traffic(self, name: str) -> float:
        try:
            user = await self.get_client(name)
            used = (
                user.get('used_traffic', 0)
                or user.get('lifetime_used_traffic', 0)
                or 0
            )
            return round(used / (1024 ** 3), 2)
        except Exception as e:
            log.error('Error get Marzban user traffic', exc_info=e)
            return 0.0

    async def add_client(
        self, name, limit_ip, limit_gb,
        expire_at: datetime.datetime = None
    ) -> dict:
        username = self._make_username(name)
        inbound_tag = await self._resolve_inbound_tag()
        if expire_at is None:
            expire_ts = int(
                (datetime.datetime.now()
                + datetime.timedelta(days=27000)).timestamp()
            )
        else:
            expire_ts = int(expire_at.timestamp())

        payload = {
            'username': username,
            'proxies': {
                'vless': {'flow': ''}
            },
            'inbounds': {
                'vless': [inbound_tag]
            },
            'expire': expire_ts,
            'data_limit': limit_gb * 1073741824 if limit_gb else 0,
            'data_limit_reset_strategy': 'month',
            'status': 'active',
        }
        resp = await self.client.post('/api/user', json=payload)
        resp.raise_for_status()
        return resp.json()

    async def delete_client(self, name) -> bool:
        username = self._make_username(name)
        resp = await self.client.delete(f'/api/user/{username}')
        if resp.status_code == 404:
            return True
        resp.raise_for_status()
        return True

    async def update_user_expire(
        self, name: str, expire_at: datetime.datetime
    ):
        username = self._make_username(name)
        expire_ts = int(expire_at.timestamp())
        resp = await self.client.put(
            f'/api/user/{username}',
            json={'expire': expire_ts, 'status': 'active'}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    async def get_user_devices(self, name) -> list:
        return []

    async def remove_user_devices(self, name, device_id):
        return False

    async def get_key_user(
        self, name, name_key,
        expire_at: datetime.datetime = None,
        limit_gb: int | None = None
    ):
        username = self._make_username(name)
        try:
            user = await self.get_client(name)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                if self.free_server:
                    resolved_limit_gb = CONFIG.limit_gb_free
                    limit_ip = CONFIG.limit_ip
                else:
                    resolved_limit_gb = CONFIG.limit_GB
                    limit_ip = CONFIG.limit_ip
                if limit_gb is not None:
                    resolved_limit_gb = int(limit_gb)
                user = await self.add_client(
                    name, limit_ip, resolved_limit_gb, expire_at
                )
            else:
                raise
        user = await self._ensure_compatible_vless_flow(name, user)
        sub_url = user.get('subscription_url', '')
        if sub_url and not sub_url.startswith('http'):
            sub_url = f'{self.base_url}{sub_url}'
        return sub_url
