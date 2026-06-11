"""Реестр каналов доставки — единая точка получения канала по виду.

Тесты подменяют каналы на in-memory фейки через `set_channels(...)`.
"""

from __future__ import annotations

from app.notifications.channel import ChannelKind, NotificationChannel
from app.notifications.email import EmailChannel
from app.notifications.max import MaxChannel

_channels: dict[ChannelKind, NotificationChannel] = {
    ChannelKind.EMAIL: EmailChannel(),
    ChannelKind.MAX: MaxChannel(),
}


def get_channel(kind: ChannelKind) -> NotificationChannel:
    return _channels[kind]


def set_channels(channels: dict[ChannelKind, NotificationChannel]) -> None:
    """Подмена каналов (для тестов)."""
    global _channels
    _channels = channels
