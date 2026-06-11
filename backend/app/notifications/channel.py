"""Подключаемые каналы доставки уведомлений (§13.4.1).

Канал доставляет ГОТОВОЕ сообщение конкретному адресату. Формирование текста,
выбор получателей и идемпотентность лежат ВЫШЕ канала (слой оркестрации). Это
позволяет добавить push/SMS, не трогая бизнес-логику графика.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ChannelKind(StrEnum):
    EMAIL = "email"
    MAX = "max"
    # PUSH = "push"   # задел, не реализуется
    # SMS  = "sms"    # задел, не реализуется


class DeliveryStatus(StrEnum):
    DELIVERED = "delivered"  # канал подтвердил приём
    FAILED = "failed"  # доставка не удалась (best-effort каналам не критично)
    SKIPPED = "skipped"  # нет адреса/привязки для этого канала


@dataclass(frozen=True)
class Attachment:
    filename: str
    size: int
    content_type: str
    storage_path: str  # путь в файловом хранилище
    public_url: str  # ссылка для скачивания (используется при деградации в MAX)


@dataclass(frozen=True)
class Message:
    subject: str  # тема (для e-mail); MAX игнорирует
    body_text: str  # текст уведомления (рус.)
    body_html: str | None = None  # html-версия для e-mail
    attachments: list[Attachment] = field(default_factory=list)
    task_code: str = ""  # 6-значный код — для удобства поиска получателем


@dataclass(frozen=True)
class Recipient:
    user_id: str
    email: str  # обязательный реквизит реестра
    max_ref: str | None = None  # chat_id/телефон/идентификатор бота MAX; None → MAX недоступен


@dataclass(frozen=True)
class DeliveryResult:
    channel: ChannelKind
    status: DeliveryStatus
    detail: str | None = None


@runtime_checkable
class NotificationChannel(Protocol):
    kind: ChannelKind

    def can_send(self, r: Recipient) -> bool: ...

    async def send(self, r: Recipient, m: Message) -> DeliveryResult: ...


# Порядок доставки для события «постановка»: сначала почта, потом MAX (§9, §13.4.1).
CHANNEL_ORDER: list[ChannelKind] = [ChannelKind.EMAIL, ChannelKind.MAX]
