"""In-memory фейковые каналы доставки (§13.7.2). Никаких реальных SMTP/MAX."""

from __future__ import annotations

from app.notifications.channel import (
    ChannelKind,
    DeliveryResult,
    DeliveryStatus,
    Message,
    Recipient,
)


class FakeChannel:
    def __init__(self, kind: ChannelKind, *, fail: bool = False, available: bool = True) -> None:
        self.kind = kind
        self.sent: list[dict] = []
        self._fail = fail
        self._available = available

    def can_send(self, r: Recipient) -> bool:
        if self.kind == ChannelKind.EMAIL:
            return self._available and bool(r.email)
        return self._available and bool(r.max_ref)

    async def send(self, r: Recipient, m: Message) -> DeliveryResult:
        self.sent.append(
            {
                "channel": self.kind,
                "to": r.email,
                "max_ref": r.max_ref,
                "subject": m.subject,
                "body": m.body_text,
            }
        )
        if self._fail:
            return DeliveryResult(self.kind, DeliveryStatus.FAILED, "fake failure")
        return DeliveryResult(self.kind, DeliveryStatus.DELIVERED)

    def recipients(self) -> list[str]:
        return [s["to"] for s in self.sent]


class FakeSocket:
    """Минимальный фейк WebSocket для тестов ConnectionManager/доставки чата.

    Реализует только `send_json`; накапливает полученные payload-ы. Опционально
    имитирует обрыв соединения (исключение при отправке), чтобы проверить, что
    рассылка остальным не срывается.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.received: list[dict] = []
        self._fail = fail

    async def send_json(self, data: dict) -> None:
        if self._fail:
            raise RuntimeError("socket closed")
        self.received.append(data)

    def types(self) -> list[str]:
        return [m.get("type") for m in self.received]

