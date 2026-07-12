import random
import string
import logging

from abc import ABC

import pyxui_async.errors

from bot.misc.VPN.BaseVpn import BaseVpn
from bot.misc.VPN.Xui.CompatXUI import CompatXUI
from bot.misc.util import CONFIG


log = logging.getLogger(__name__)


class XuiBase(BaseVpn, ABC):

    NAME_VPN: str
    POST_FIX: str

    def __init__(self, server, timeout):
        if server.connection_method:
            self.type_con = 'https://'
        else:
            self.type_con = 'http://'
        full_address = f'{self.type_con}{server.ip}'
        self.xui = CompatXUI(
            full_address=full_address,
            panel='sanaei',
            https=server.connection_method,
            timeout=timeout,
        )
        self.inbound_id = int(server.inbound_id)
        self.login_user = server.login
        self.password = server.password
        self.free_server = server.free_server
        self.xui.additional_inbound_ids = []

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

    async def restore_client_access(self, email: str, limit_gb: int | None = None):
        client = await self.get_client(email)
        if client is None:
            log.warning(
                'event=xui_client_restore status=missing inbound_id=%s email=%s',
                self.inbound_id,
                email,
            )
            return 'missing'

        resolved_limit_gb = limit_gb
        if resolved_limit_gb is None:
            configured_limit = int(getattr(CONFIG, 'limit_GB', 0) or 0)
            resolved_limit_gb = configured_limit if configured_limit > 0 else 1000
        limit_bytes = int(resolved_limit_gb) * 1073741824

        response = await self.xui.update_client(
            inbound_id=self.inbound_id,
            email=email,
            uuid=getattr(client, 'id', None),
            enable=True,
            flow=getattr(client, 'flow', None),
            limit_ip=getattr(client, 'limitIp', None),
            total_gb=limit_bytes,
            expire_time=getattr(client, 'expiryTime', None),
            telegram_id=getattr(client, 'tgId', None),
            subscription_id=getattr(client, 'subId', None),
        )
        if not getattr(response, 'success', False):
            log.error(
                'event=xui_client_restore status=update_failed inbound_id=%s email=%s message=%s',
                self.inbound_id,
                email,
                getattr(response, 'msg', ''),
            )
            return 'failed'

        reset_response = await self.xui.reset_client_traffic(
            inbound_id=self.inbound_id,
            email=email,
        )
        if not getattr(reset_response, 'success', False):
            log.error(
                'event=xui_client_restore status=reset_failed inbound_id=%s email=%s message=%s',
                self.inbound_id,
                email,
                getattr(reset_response, 'msg', ''),
            )
            return 'failed'

        log.info(
            'event=xui_client_restore status=restored inbound_id=%s email=%s limit_gb=%s',
            self.inbound_id,
            email,
            resolved_limit_gb,
        )
        return 'restored'

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
