import logging as logger
from tenacity import retry, stop_after_attempt

from ..AmneziaWG import AmneziaWGClient, ensure_authenticated
from .models import ClientModel


class WireGuardClient(AmneziaWGClient):

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
