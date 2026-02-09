import json

from bot.misc.VPN.AmneziaWireGuardClients import AmneziaWGClient
from bot.misc.VPN.BaseVpn import BaseVpn
from bot.misc.util import CONFIG


class AmneziaWG(BaseVpn):
    NAME_VPN = 'AmneziaWG 🐉'
    POST_FIX = 'am'
    client: AmneziaWGClient

    def __init__(self, server, timeout):
        api_cert = json.loads(server.outline_link)
        self.url = api_cert['url']
        self.password = api_cert['password']
        self.free_server = server.free_server

    async def login(self):
        self.client = AmneziaWGClient(
            url=self.url, password=self.password, timeout=30
        )
        await self.client.authenticate()

    async def get_all_user_server(self):
        return await self.client.get_clients()

    async def get_client(self, name):
        return await self.client.get_client(name)

    async def get_client_traffic(self, name):
        client = await self.get_client(name)
        return client.transfer_rx

    async def add_client(self, name, limit_ip, limit_gb):
        return await self.client.create_client(name)

    async def delete_client(self, telegram_id):
        client = await self.get_client(telegram_id)
        if client is not None:
            return await self.client.delete_client(client.id)
        return True

    async def get_user_devices(self, name):
        return None

    async def remove_user_devices(self, name, device_id):
        return None

    async def get_key_user(self, name, name_key):
        client = await self.get_client(name)
        if client is None:
            if self.free_server:
                await self.add_client(
                    name, CONFIG.limit_ip, CONFIG.limit_gb_free
                )
            else:
                await self.add_client(name, CONFIG.limit_ip, CONFIG.limit_GB)
            client = await self.get_client(name)
        key = await self.client.get_configuration(client.id)
        return await self.update_key_name(key, name_key)

    async def update_key_name(self, key, name_key):
        try:
            return dict(config=key, name_key=name_key)
        except Exception as e:
            print(e)
        return key
