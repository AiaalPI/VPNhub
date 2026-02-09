import base64
import json
import os

import pyxui_async.errors
from pyxui_async import ClientSettings, Client

from bot.misc.VPN.Xui.XuiBase import XuiBase
from bot.misc.util import CONFIG


class Trojan(XuiBase):
    NAME_VPN = 'Trojan 🏇'
    POST_FIX = 'tr'
    adress: str

    def __init__(self, server, timeout):
        super().__init__(server, timeout)

    async def add_client(self, name, limit_ip, limit_gb):
        try:
            response = await self.xui.add_clients(
                inbound_id=self.inbound_id,
                client_settings=ClientSettings(
                    clients=[
                        Client(
                            email=str(name),
                            limitIp=limit_ip,
                            totalGB=limit_gb * 1073741824,
                            subId=self.random_lower_and_num(16),
                            password=self.random_lower_and_num(10),
                        )
                    ]
                )
            )
            if response.success:
                return True
            return False
        except pyxui_async.errors.NotFound:
            return False

    async def get_key_user(self, name, name_key):
        client = await self.get_client(name)
        if client is None:
            if self.free_server:
                await self.add_client(
                    name, CONFIG.limit_ip, CONFIG.limit_gb_free
                )
            else:
                await self.add_client(name, CONFIG.limit_ip, CONFIG.limit_GB)
        return await self.xui.get_key_trojan(
            inbound_id=self.inbound_id,
            email=name,
            custom_remark=name_key
        )
