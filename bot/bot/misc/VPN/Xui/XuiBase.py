import random
import string

from abc import ABC

from pyxui_async import XUI
import pyxui_async.errors

from bot.misc.VPN.BaseVpn import BaseVpn


class XuiBase(BaseVpn, ABC):

    NAME_VPN: str
    POST_FIX: str

    def __init__(self, server, timeout):
        if server.connection_method:
            self.type_con = 'https://'
        else:
            self.type_con = 'http://'
        full_address = f'{self.type_con}{server.ip}'
        self.xui = XUI(
            full_address=full_address,
            panel='sanaei',
            https=server.connection_method,
            timeout=timeout,
        )
        self.inbound_id = int(server.inbound_id)
        self.login_user = server.login
        self.password = server.password
        self.free_server = server.free_server

    async def login(self):
        await self.xui.login(username=self.login_user, password=self.password)

    async def get_inbound(self):
        try:
            return await self.xui.get_inbound(inbound_id=self.inbound_id)
        except pyxui_async.errors.NotFound:
            return None

    async def get_all_user_server(self):
        try:
            inbounds = await self.xui.get_inbounds()
            for inbound in inbounds.obj:
                if inbound.id == self.inbound_id:
                    return inbound.clientStats
            raise IndexError('Inbound ID not found')
        except IndexError:
            return None

    async def get_client_traffic(self, name):
        try:
            client_stats =  await self.xui.get_client_stat(
                inbound_id=self.inbound_id,
                email=name,
            )
            if client_stats is None:
                raise pyxui_async.errors.NotFound()
            bytes_size = client_stats.up + client_stats.down
            return round(bytes_size / (1024 ** 3), 2)
        except pyxui_async.errors.NotFound:
            return None

    async def get_client(self, name):
        try:
            return await self.xui.get_client(
                inbound_id=self.inbound_id,
                email=name,
            )
        except pyxui_async.errors.NotFound:
            return None


    async def delete_client(self, telegram_id):
        try:
            response = await self.xui.delete_client(
                inbound_id=self.inbound_id,
                email=telegram_id,
            )
            return response
        except pyxui_async.errors.NotFound:
            return True

    async def get_user_devices(self, name):
        return None

    async def remove_user_devices(self, name, device_id):
        return None

    def random_lower_and_num(self, length):
        seq = string.ascii_lowercase + string.digits
        result = ''.join(random.choice(seq) for _ in range(length))
        return result
