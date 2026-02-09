import asyncio

import aiohttp
import logging as logger
from tenacity import retry, stop_after_attempt

from aiohttp import ClientTimeout

from .models import ClientModel


def ensure_authenticated(func):
    async def wrapper(self, *args, **kwargs):
        if not self.cookies or not self.session:
            raise RuntimeError('Not logged in. Call `authenticate()`')
        return await func(self, *args, **kwargs)

    return wrapper


class AmneziaWGClient:
    def __init__(self, url, password, timeout=10):
        self.session = None
        self.cookies = None
        self.api_url = url
        self.password = password
        self.timeout = ClientTimeout(total=timeout)

    @retry(stop=stop_after_attempt(3))
    async def authenticate(self) -> bool:
        """
        Аутентификация и создание сессии.
        :return: bool
        """
        self.session = aiohttp.ClientSession()
        payload = {
            "password": self.password,
            "remember": True
        }
        try:
            async with self.session.post(
                f"{self.api_url}/api/session",
                json=payload,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                self.cookies = resp.cookies
                logger.debug('The AmnesiaWG authorization is successful.')
                return True
        except Exception as e:
            logger.exception(
                f'Error connecting to AmneziaWG', exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def create_client(self, name:str, expired_date='') -> bool:
        """
        Создание нового пользователя.
        :param name: str имя ключа
        :param expired_date: str дата окончания, например 2026-01-01
        :return: bool
        """
        payload = {
            "name": name,
            "expiredDate": expired_date
        }
        try:
            async with self.session.post(
                f"{self.api_url}/api/wireguard/client",
                json=payload,
                cookies=self.cookies,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(f'Client {name} has been successfully created.')
                return True
        except Exception as e:
            logger.error(
                f'Error when creating the client {name}', exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def get_clients(self) -> list[ClientModel]:
        """
        Получения списка всех клиентов сервера.
        :return: list[ClientModel] список клиентов
        """
        try:
            async with self.session.get(
                f"{self.api_url}/api/wireguard/client",
                cookies=self.cookies,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                logger.debug('The list of clients was received successfully.')
                return [ClientModel(**client) for client in data]
        except Exception as e:
            logger.error(
                'Error when receiving the list of clients',
                exc_info=e
            )
            return []

    async def get_client(self, name_client:str) -> ClientModel | None:
        """
        Получение информации о клиенте
        :param name_client: str имя клиента
        :return: ClientModel | None
        """
        all_clients = await self.get_clients()
        for client in all_clients:
            if client.name == name_client:
                return client
        return None

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def delete_client(self, client_id:str) -> bool:
        """
        Удаление клиента с сервера.
        :param client_id: str  uuid клиента
        :return: bool
        """
        try:
            async with self.session.delete(
                f"{self.api_url}/api/wireguard/client/{client_id}",
                cookies=self.cookies,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(
                    f'Client {client_id} has been successfully deleted.'
                )
                return True
        except Exception as e:
            logger.error(
                f'Error deleting the client {client_id}',
                exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def get_configuration(self, client_id: str) -> str | None:
        """
        Получение конфигурации пользователя.
        :param client_id: str  uuid клиента
        :return: str
        """
        try:
            async with self.session.get(
                f"{self.api_url}/api/wireguard/client/"
                f"{client_id}/configuration",
                cookies=self.cookies,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                config = await resp.text()
                logger.debug(
                    f'the configuration for the client {client_id} '
                    f'has been successfully received.'
                )
                return config
        except Exception as e:
            logger.error(
                f'Error receiving configuration for client {client_id}',
                exc_info=e
            )
            return None

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def get_configuration_qrcode(self, client_id: str) -> str | None:
        """
        Получение конфигурации пользователя в виде svg QR кода.
        :param client_id: str  uuid клиента
        :return: str
        """
        try:
            async with self.session.get(
                    f"{self.api_url}/api/wireguard/client/"
                    f"{client_id}/qrcode.svg",
                    cookies=self.cookies,
                    timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                config = await resp.text()
                logger.debug(
                    f'the configuration QR code for the client {client_id} '
                    f'has been successfully received.'
                )
                return config
        except Exception as e:
            logger.error(
                f'Error receiving configuration QR code '
                f'for client {client_id}',
                exc_info=e
            )
            return None

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def disable_client(self, client_id: str) -> bool:
        """
        Выключение клиента.
        :param client_id: str  uuid клиента
        :return: bool
        """
        try:
            async with self.session.post(
                f"{self.api_url}/api/wireguard/client/{client_id}/disable",
                cookies=self.cookies,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(
                    f'Client {client_id} has been successfully disable.'
                )
                return True
        except Exception as e:
            logger.error(
                f'Error disable the client {client_id}',
                exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def enable_client(self, client_id: str) -> bool:
        """
        Включение клиента.
        :param client_id: str  uuid клиента
        :return: bool
        """
        try:
            async with self.session.post(
                f"{self.api_url}/api/wireguard/client/{client_id}/enable",
                cookies=self.cookies,
                timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(
                    f'Client {client_id} has been successfully enable.'
                )
                return True
        except Exception as e:
            logger.error(
                f'Error enable the client {client_id}',
                exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def update_client_name(self, client_id: str, name: str) -> bool:
        """
        Изменение имени клиента.
        :param client_id: str  uuid клиента
        :param name: str новое имя
        :return: bool
        """
        try:
            payload = {
                "name": name,
            }
            async with self.session.put(
                    f"{self.api_url}/api/wireguard/client/{client_id}/name",
                    cookies=self.cookies,
                    json=payload,
                    timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(
                    f'Client {client_id} has been successfully new name'
                )
                return True
        except Exception as e:
            logger.error(
                f'Error update name the client {client_id}',
                exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def update_client_address(self, client_id: str, address: str) -> bool:
        """
        Изменение адреса клиента.
        :param client_id: str  uuid клиента
        :param address: str новый адрес
        :return: bool
        """
        try:
            payload = {
                "address": address,
            }
            async with self.session.put(
                    f"{self.api_url}/api/wireguard/client/{client_id}/address",
                    cookies=self.cookies,
                    json=payload,
                    timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(
                    f'Client {client_id} has been successfully new address'
                )
                return True
        except Exception as e:
            logger.error(
                f'Error update address the client {client_id}',
                exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def update_client_expire_date(
        self,
        client_id: str,
        expire_date: str
    ) -> bool:
        """
        Изменение времени действия ключа у клиента.
        :param client_id: str  uuid клиента
        :param expire_date: str новый адрес
        :return: bool
        """
        try:
            payload = {
                "expireDate": expire_date,
            }
            async with self.session.put(
                    f"{self.api_url}/api/wireguard/client"
                    f"/{client_id}/expireDate",
                    cookies=self.cookies,
                    json=payload,
                    timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                logger.debug(
                    f'Client {client_id} has been successfully new expire date'
                )
                return True
        except Exception as e:
            logger.error(
                f'Error update expire date the client {client_id}',
                exc_info=e
            )
            return False

    @ensure_authenticated
    @retry(stop=stop_after_attempt(3))
    async def get_backup_config(self) -> str | None:
        """
        Получение резервной копии.
        :return: str
        """
        try:
            async with self.session.get(
                    f"{self.api_url}/api/wireguard/backup",
                    cookies=self.cookies,
                    timeout=self.timeout
            ) as resp:
                resp.raise_for_status()
                config = await resp.text()
                logger.debug('backup copy received')
                return config
        except Exception as e:
            logger.error('Error in getting a backup copy',exc_info=e)
            return None

    async def close(self):
        """
        Закрытие сессии.
        :return:
        """
        if self.session:
            await self.session.close()
            logger.debug("Session close.")

    async def _close(self):
        await self.session.close()
        logger.debug("Session close.")

    def __del__(self):
        if self.session is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._close())
            return
        loop.create_task(self._close())
