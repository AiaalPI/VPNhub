import uuid

import pyxui_async.errors
from pyxui_async import ClientSettings, Client

from bot.misc.VPN.Xui.XuiBase import XuiBase
from bot.misc.util import CONFIG


class Vless(XuiBase):
    NAME_VPN = 'Vless 🐊'
    POST_FIX = 'vl'

    def __init__(self, server, timeout):
        super().__init__(server, timeout)

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

    async def get_key_user(self, name, name_key):
        client = await self.get_client(name)
        if client is None:
            if self.free_server:
                await self.add_client(
                    name, CONFIG.limit_ip, CONFIG.limit_gb_free
                )
            else:
                await self.add_client(name, CONFIG.limit_ip, CONFIG.limit_GB)
        return await self.xui.get_key_vless(
            inbound_id=self.inbound_id,
            email=name,
            custom_remark=name_key
        )
