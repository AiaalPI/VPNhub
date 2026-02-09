import json

from outline_vpn import OutlineVPN

from bot.misc.VPN.BaseVpn import BaseVpn
from bot.misc.util import CONFIG


class Outline(BaseVpn):
    NAME_VPN = 'Outline 🪐'
    POST_FIX = 'ou'
    client_outline: OutlineVPN

    def __init__(self, server, timeout):
        api_cert = json.loads(server.outline_link)
        self.api_url = api_cert['apiUrl']
        self.cert_sha256 = api_cert['certSha256']
        self.free_server = server.free_server

    async def login(self):
        self.client_outline = OutlineVPN(api_url=self.api_url)
        await self.client_outline.init(self.cert_sha256)

    async def get_all_user_server(self):
        return await self.client_outline.get_keys()

    async def get_client(self, name):
        all_user = await self.get_all_user_server()
        for user in all_user:
            if user.name == str(name):
                return user
        return None

    async def get_client_traffic(self, name):
        return 0.0

    async def add_client(self, name, limit_ip, limit_gb):
        try:
            key = await self.client_outline.create_key(key_name=name)
            if CONFIG.limit_GB != 0:
                await self.client_outline.add_data_limit(
                    key.key_id,
                    limit_gb * 10 ** 9
                )
            return key
        except Exception as e:
            print(e, 'Outline.py Line 32')
            return False

    async def delete_client(self, telegram_id):
        client = await self.get_client(telegram_id)
        if client is not None:
            await self.client_outline.delete_key(key_id=client.key_id)

    async def get_key_user(self, name, name_key):
        client = await self.get_client(name)
        if client is None:
            if self.free_server:
                key = await self.add_client(
                    name, CONFIG.limit_ip, CONFIG.limit_gb_free
                )
            else:
                key = await self.add_client(
                    name, CONFIG.limit_ip, CONFIG.limit_GB
                )

            return await self.update_key_name(key.access_url, name_key)
        return await self.update_key_name(client.access_url, name_key)

    async def get_user_devices(self, name):
        return None

    async def remove_user_devices(self, name, device_id):
        return None

    async def update_key_name(self, key, name_key):
        try:
            return key.replace(
                '?outline=1',
                f'?outline=1&prefix=%16%03%01%00%C2%A8%01%01#{name_key}'
            )
        except Exception as e:
            print(e)
        return key
