import logging
from datetime import timezone, timedelta, datetime

from bot.misc.VPN.Amnezia_wg import AmneziaWG
from bot.misc.VPN.Remnawave import Remnawave
from bot.misc.VPN.Xui.Trojan import Trojan
from bot.misc.VPN.Xui.Vless import Vless
from bot.misc.VPN.Xui.Shadowsocks import Shadowsocks
from bot.misc.VPN.Outline import Outline
from bot.misc.VPN.Xui.WireGuard import WireGuard
from bot.misc.util import CONFIG

log = logging.getLogger(__name__)


class ServerManager:
    VPN_TYPES = {
        0: Outline,
        1: Vless,
        2: Shadowsocks,
        3: WireGuard,
        4: AmneziaWG,
        5: Trojan,
        6: Remnawave
    }

    def __init__(self, server, timeout=30):
        try:
            self.client = self.VPN_TYPES.get(server.type_vpn)(server, timeout)
        except Exception as e:
            log.error('Error initializing ServerManager: ', exc_info=e)

    async def login(self):
        await self.client.login()

    async def get_all_user(self):
        try:
            return await self.client.get_all_user_server()
        except Exception as e:
            log.error('Error get all user server', exc_info=e)
            return None

    async def get_user(self, name, key_id):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            return await self.client.get_client(str(name_str))
        except Exception as e:
            log.error('Error get user server', exc_info=e)

    async def get_client_traffic(self, name, key_id):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            return await self.client.get_client_traffic(str(name_str))
        except Exception as e:
            log.error('Error get user server', exc_info=e)

    async def add_client(
        self,
        name,
        key_id,
        limit_ip=CONFIG.limit_ip,
        limit_gb=CONFIG.limit_GB
    ):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            return await self.client.add_client(str(name_str), limit_ip, limit_gb)
        except Exception as e:
            log.error('Error add client server', exc_info=e)

    async def delete_client(self, name, key_id):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            await self.client.delete_client(str(name_str))
            return True
        except Exception as e:
            log.error('Error delete client server', exc_info=e)
            return False

    async def get_user_devices(self, name, key_id):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            return await self.client.get_user_devices(str(name_str))
        except Exception as e:
            log.error('Error get devices client server', exc_info=e)
            return None


    async def remove_user_devices(self, name, key_id, device_id):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            return await self.client.remove_user_devices(
                str(name_str), device_id
            )
        except Exception as e:
            log.error('Error remove device client server', exc_info=e)
            return None

    async def get_key(self, name, name_key, key_id, subscription_timestamp=None):
        try:
            name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
            name_key = CONFIG.name + ' | ' + name_key
            kwargs = {}
            expire_at = None

            if subscription_timestamp is not None and isinstance(
                    self.client, Remnawave
            ):
                utc_plus = timezone(timedelta(hours=CONFIG.UTC_time))
                expire_at = datetime.fromtimestamp(
                    subscription_timestamp, tz=utc_plus
                )

            if expire_at is not None:
                kwargs['expire_at'] = expire_at
            return await self.client.get_key_user(
                str(name_str), str(name_key), **kwargs
            )
        except Exception as e:
            log.error('Error get key server', exc_info=e)


    async def update_user_expire(self, name, key_id, expire_at):
        try:
            if hasattr(self.client, 'update_user_expire'):
                name_str = f'{name}.{key_id}.{self.client.POST_FIX}'
                return await self.client.update_user_expire(
                    str(name_str), expire_at
                )
            return None
        except Exception as e:
            log.error('Error update user expire: %s', str(e))
            return None
