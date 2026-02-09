from pydantic import BaseModel

from bot.misc.VPN.Xui.XuiBase import XuiBase


class WireGuardKey(BaseModel):
    key: str
    name_key: str
    public_key: str


class WireGuard(XuiBase):
    NAME_VPN = 'WireGuard 🦎'
    POST_FIX = 'wg'

    def __init__(self, server, timeout):
        super().__init__(server, timeout)

    async def add_client(self, name, limit_ip, limit_gb):
        result =  await self.xui.add_client_wg(inbound_id=self.inbound_id)
        return result['new_peer'].publicKey

    async def delete_client(self, telegram_id):
        public_key = telegram_id.split('.')[0]
        response = await self.xui.delete_client_wg(
            inbound_id=self.inbound_id,
            user_public_key=public_key
        )
        return response

    async def get_client(self, name):
        public_key = name.split('.')[0]
        peers = None
        try:
            inbounds = await self.xui.get_inbounds()
            for inbound in inbounds.obj:
                if inbound.id == self.inbound_id:
                    peers = inbound.settings.peers
            if peers is None:
                raise IndexError('Inbound ID not found')
            for peer in peers:
                if peer.publicKey == public_key:
                    return peer
            raise IndexError('User not found')
        except IndexError:
            return None

    async def get_all_user_server(self):
        try:
            inbounds = await self.xui.get_inbounds()
            for inbound in inbounds.obj:
                if inbound.id == self.inbound_id:
                    return inbound.settings.peers
            raise IndexError('Inbound ID not found')
        except IndexError:
            return None

    async def get_client_traffic(self, name):
        return None

    async def get_key_user(self, name, name_key) -> WireGuardKey:
        public_key = name.split('.')[0]
        client = await self.xui.get_key_client_wg(
            inbound_id=self.inbound_id,
            user_public_key=public_key
        )
        if len(client) == 0:
            result = await self.add_client(name, None, None)
            client = await self.xui.get_key_client_wg(
                inbound_id=self.inbound_id,
                user_public_key=result
            )
            public_key = result
        return WireGuardKey(
            key=client[public_key], public_key=public_key, name_key=name_key
        )
