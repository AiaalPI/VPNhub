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
    INBOUND_TAG = 'VLESS_REALITY'

    def __init__(self, server: Servers, timeout=30):
        self.free_server = server.free_server
        self.timeout = timeout
        self.base_url = server.panel.rstrip('/')
        self.username = server.login
        self.password = server.password
        self.token: str | None = None
        self.client: httpx.AsyncClient | None = None

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

    async def get_all_user_server(self) -> list[dict]:
        offset = 0
        limit = 100
        users = []
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
                'vless': {'flow': 'xtls-rprx-vision'}
            },
            'inbounds': {
                'vless': [self.INBOUND_TAG]
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
        sub_url = user.get('subscription_url', '')
        if sub_url and not sub_url.startswith('http'):
            sub_url = f'{self.base_url}{sub_url}'
        return sub_url
