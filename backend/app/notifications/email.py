"""E-mail-канал — обязательный и гарантированный (§13.4.1)."""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import aiosmtplib

from app.core.config import settings
from app.notifications.channel import (
    ChannelKind,
    DeliveryResult,
    DeliveryStatus,
    Message,
    Recipient,
)


class EmailChannel:
    kind = ChannelKind.EMAIL

    def can_send(self, r: Recipient) -> bool:
        return bool(r.email)

    async def send(self, r: Recipient, m: Message) -> DeliveryResult:
        if not self.can_send(r):
            return DeliveryResult(self.kind, DeliveryStatus.SKIPPED, "no email")
        try:
            msg = EmailMessage()
            msg["From"] = settings.smtp_from
            msg["To"] = r.email
            msg["Subject"] = m.subject
            msg.set_content(m.body_text)
            if m.body_html:
                msg.add_alternative(m.body_html, subtype="html")
            for att in m.attachments:
                data = Path(att.storage_path).read_bytes()
                maintype, _, subtype = (att.content_type or "application/octet-stream").partition(
                    "/"
                )
                msg.add_attachment(
                    data,
                    maintype=maintype or "application",
                    subtype=subtype or "octet-stream",
                    filename=att.filename,
                )
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                use_tls=settings.smtp_tls,
                timeout=20,
            )
            return DeliveryResult(self.kind, DeliveryStatus.DELIVERED)
        except Exception as exc:  # noqa: BLE001 — гарантированный канал: помечаем для ретрая
            return DeliveryResult(self.kind, DeliveryStatus.FAILED, str(exc)[:300])
