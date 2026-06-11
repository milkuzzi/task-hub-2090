"""MAX-канал — best-effort (§13.4.1).

MAX принимает не все типы файлов (HTML не проходит). Проблемные вложения
заменяются ссылкой в теле и дублируются почтой (почта шлёт все файлы первой).
Любой сбой проглатывается и не блокирует обязательный канал.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from app.core.config import settings
from app.notifications.channel import (
    Attachment,
    ChannelKind,
    DeliveryResult,
    DeliveryStatus,
    Message,
    Recipient,
)


def _split_attachments(m: Message) -> tuple[str, list[Attachment]]:
    blocked = settings.max_blocked_ext_set
    max_size = settings.max_file_size_mb * 1024 * 1024
    sendable: list[Attachment] = []
    degraded: list[Attachment] = []
    for a in m.attachments:
        ext = Path(a.filename).suffix.lower()
        if ext in blocked or a.size > max_size:
            degraded.append(a)
        else:
            sendable.append(a)
    body = m.body_text
    if degraded:
        links = "\n".join(f"• {a.filename}: {a.public_url}" for a in degraded)
        body += (
            "\n\nЧасть вложений недоступна в MAX, они отправлены на почту "
            f"и доступны по ссылке:\n{links}"
        )
    return body, sendable


class MaxChannel:
    kind = ChannelKind.MAX

    def can_send(self, r: Recipient) -> bool:
        return settings.max_enabled and bool(r.max_ref) and bool(settings.max_api_base)

    async def send(self, r: Recipient, m: Message) -> DeliveryResult:
        if not self.can_send(r):
            return DeliveryResult(self.kind, DeliveryStatus.SKIPPED, "no max binding")
        try:
            body, _sendable = _split_attachments(m)
            payload = {"chat_id": r.max_ref, "text": body}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{settings.max_api_base.rstrip('/')}/sendMessage",
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.max_bot_token}"},
                )
            if resp.status_code >= 400:
                return DeliveryResult(self.kind, DeliveryStatus.FAILED, f"http {resp.status_code}")
            return DeliveryResult(self.kind, DeliveryStatus.DELIVERED)
        except Exception as exc:  # noqa: BLE001 — best-effort: сбой не критичен
            return DeliveryResult(self.kind, DeliveryStatus.FAILED, str(exc)[:300])
