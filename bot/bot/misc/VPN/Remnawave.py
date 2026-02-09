import datetime
import httpx
import logging

from urllib.parse import urlparse
from uuid import UUID

from remnawave import RemnawaveSDK
from remnawave.enums import TrafficLimitStrategy
from remnawave.exceptions import NotFoundError, ConflictError
from remnawave.models import (
    UsersResponseDto,
    UserResponseDto,
    CreateUserRequestDto,
    DeleteUserResponseDto,
    GetAllInternalSquadsResponseDto, UpdateUserRequestDto
)
from remnawave.models.hwid import HwidDeviceDto, DeleteUserHwidDeviceRequestDto

from bot.database.models.main import Servers
from bot.misc.VPN.BaseVpn import BaseVpn
from bot.misc.util import CONFIG


class Remnawave(BaseVpn):
    NAME_VPN = 'Remnawave 🌊'
    POST_FIX = 're'
    BASE_URL: str
    TOKEN: str
    URL_LOGIN: str
    CLIENT: RemnawaveSDK

    def __init__(self, server: Servers, timeout):
        self.free_server = server.free_server
        self.timeout = timeout
        self.BASE_URL = server.ip + '/api'
        self.TOKEN = server.login
        self.URL_LOGIN = server.password
        self.BASE_URL_NOT_API = server.ip
        self.SQUAD_ID = server.remnawave_squad_id

    async def login(self):
        if self.URL_LOGIN is not None:
            url = urlparse(self.URL_LOGIN)
            result = url.path
            if url.query:
                result += "?" + url.query
            if "caddy=" not in url.query:
                params = {url.query.split('=')[0]: url.query.split('=')[1]}
            else:
                params = {}
            client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={'Authorization': f'Bearer {self.TOKEN}'},
                timeout=self.timeout,
                params=params
            )
            await client.get(result)
            self.CLIENT = RemnawaveSDK(client=client)
        else:
            self.CLIENT = RemnawaveSDK(
                base_url=self.BASE_URL, token=self.TOKEN
            )

    async def get_all_user_server(self) -> list[UserResponseDto]:
        all_users = []
        batch_size = 500
        first_response = await self.CLIENT.users.get_all_users(
            start=0,
            size=1
        )
        total_users = first_response.total
        for start in range(0, total_users, batch_size):
            try:
                response = await self.CLIENT.users.get_all_users(
                    start=start,
                    size=batch_size
                )
                if response.users:
                    batch_users = list(response.users)
                    all_users.extend(batch_users)

            except Exception as e:
                logging.error('Error get users', exc_info=e)
                break
        if self.SQUAD_ID is not None:
            internal_squad_user = []
            for user in all_users:
                for squad in user.active_internal_squads:
                    if str(squad.uuid) == self.SQUAD_ID:
                        internal_squad_user.append(user)
            return internal_squad_user
        return all_users

    async def get_client(self, name) -> UserResponseDto:
        username = name.replace(".", "_")
        return await self.CLIENT.users.get_user_by_username(username)

    async def get_client_traffic(self, name):
        try:
            user = await self.get_client(name)
            return round(user.used_traffic_bytes / (1024 ** 3), 2)
        except Exception as e:
            logging.error('Error get user server', exc_info=e)
            return 0.0

    async def add_client(
        self, name, limit_ip, limit_gb, expire_at: datetime.datetime = None
    ) ->  CreateUserRequestDto:
        username = name.replace(".", "_")
        telegram_id = name.split(".")[0]
        squad_uuid = await self.get_squad_uuid()
        if telegram_id.isdigit():
            telegram_id = int(telegram_id)
        else:
            telegram_id = None
        if expire_at is None:
            expire_at = datetime.datetime.now() + datetime.timedelta(days=27000)
        return await self.CLIENT.users.create_user(CreateUserRequestDto(
            username=username,
            expire_at=expire_at,
            telegram_id=telegram_id,
            traffic_limit_bytes=limit_gb * 1073741824,
            hwid_device_limit=limit_ip,
            active_internal_squads=squad_uuid,
            traffic_limit_strategy=TrafficLimitStrategy.MONTH
        ))

    async def get_all_internal_squads(
        self
    ) -> GetAllInternalSquadsResponseDto | None:
        try:
            return await self.CLIENT.internal_squads.get_internal_squads()
        except Exception as e:
            logging.error('Error getting internal squads:', exc_info=e)
            return None

    async def get_squad_uuid(self) -> list[UUID] | None:
        squads = await self.get_all_internal_squads()
        if squads.total == 0:
            return None
        if squads.total == 1:
            return [squads.internal_squads[0].uuid]
        else:
            if self.SQUAD_ID is not None:
                for squad in squads.internal_squads:
                    if str(squad.uuid) == self.SQUAD_ID:
                        return [squad.uuid]
            return [squads.internal_squads[0].uuid]

    async def update_client_enable(self, name: str, enable: bool):
        try:
            user = await self.get_client(name)
            if enable:
                await self.CLIENT.users.enable_user(str(user.uuid))
            else:
                await self.CLIENT.users.disable_user(str(user.uuid))
            return True
        except NotFoundError:
            return True
        except ConflictError:
            return True

    async def update_user_expire(
        self, name, expire_at: datetime.datetime
    ) -> UserResponseDto:
        try:
            user = await self.get_client(name)
            return await self.CLIENT.users.update_user(UpdateUserRequestDto(
                uuid=str(user.uuid),
                expire_at=expire_at
            ))
        except NotFoundError:
            return None

    async def delete_client(self, name) -> DeleteUserResponseDto:
        try:
            user = await self.get_client(name)
            resp = await self.CLIENT.users.delete_user(str(user.uuid))
            return resp.is_deleted
        except NotFoundError:
            return True

    async def get_user_devices(self, name) -> list[HwidDeviceDto]:
        user = await self.get_client(name)
        hwid_user = await self.CLIENT.hwid.get_hwid_user(str(user.uuid))
        return hwid_user.devices

    async def remove_user_devices(self, name, device_id):
        try:
            user = await self.get_client(name)
            return await self.CLIENT.hwid.delete_hwid_to_user(
                body=DeleteUserHwidDeviceRequestDto(
                    user_uuid=str(user.uuid),
                    hwid=str(device_id),
                )
            )
        except NotFoundError:
            return False

    async def get_key_user(
        self, name, name_key, expire_at: datetime.datetime = None
    ):
        try:
            user = await self.get_client(name)
        except NotFoundError:
            if self.free_server:
                limit_gb = CONFIG.limit_gb_free
                limit_ip = CONFIG.limit_ip
            else:
                limit_gb = CONFIG.limit_GB
                limit_ip = CONFIG.limit_ip
            user = await self.add_client(name, limit_ip, limit_gb, expire_at)
        return user.subscription_url
