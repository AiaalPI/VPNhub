from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ClientModel(BaseModel):
    """
    Модель клиента
    :param id: str UUID клиента
    :param name: str Имя клиента
    :param enabled: bool Активен ли клиент
    :param address: str Внутренний IP (например, "10.8.0.2")
    :param public_key: str Публичный ключ WireGuard
    :param created_at: datetime Дата создания
    :param updated_at: datetime Дата последнего обновления
    :param expired_at: Optional[datetime] = None Дата истечения (может быть None)
    :param one_time_link: Optional[str] = None Одноразовая ссылка (если есть)
    :param one_time_link_expires_at: Optional[datetime] = None Срок действия ссылки
    :param downloadable_config: bool Доступен ли конфиг для скачивания
    :param persistent_keepalive: str Настройки keepalive ("on" / "off")
    :param latest_handshake_at: Optional[datetime] = None Последнее рукопожатие
    :param transfer_rx: int Получено данных (в байтах)
    :param transfer_tx: int Отправлено данных (в байтах)
    :param endpoint: Optional[str] = None Внешний IP:Port сервера ("85.26.235.162:24246")
    """
    id: str = Field(...)
    name: str = Field(...)
    enabled: bool = Field(...)
    address: str = Field(...)
    public_key: str = Field(..., alias="publicKey")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime | None = Field(..., alias="updatedAt")
    expired_at: datetime | None = Field(..., alias="expiredAt")
    one_time_link: str | None = Field(..., alias="oneTimeLink")
    one_time_link_expires_at: datetime | None = Field(..., alias="oneTimeLinkExpiresAt")
    downloadable_config: bool = Field(..., alias="downloadableConfig")
    persistent_keepalive: str | None = Field(..., alias="persistentKeepalive")
    latest_handshake_at: datetime | None = Field(..., alias="latestHandshakeAt")
    transfer_rx: int | None = Field(..., alias="transferRx")
    transfer_tx: int | None = Field(..., alias="transferTx")
    endpoint: str | None = Field(...)

