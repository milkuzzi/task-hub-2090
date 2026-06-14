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

            # Решаем, какие вложения инлайнить, ДО чтения файлов в память: канал
            # читает файлы целиком, поэтому крупные/суммарно тяжёлые вложения не
            # вкладываем (риск OOM на воркере 256 МБ), а заменяем ссылками в теле.
            cap = settings.max_email_attachment_mb * 1024 * 1024
            inline: list = []
            skipped: list = []
            running = 0
            for att in m.attachments:
                try:
                    size = Path(att.storage_path).stat().st_size
                except OSError:
                    size = att.size or 0
                if size > cap or running + size > cap:
                    skipped.append(att)
                else:
                    inline.append(att)
                    running += size

            body_text = m.body_text
            body_html = m.body_html
            if skipped:
                links = "\n".join(
                    f"• {att.filename}: {att.public_url}" for att in skipped
                )
                body_text += (
                    "\n\nЧасть вложений слишком велика для письма и не приложена — "
                    f"файлы доступны в приложении по ссылке:\n{links}"
                )
                if body_html:
                    html_links = "".join(
                        f"<li>{att.filename}: "
                        f'<a href="{att.public_url}">{att.public_url}</a></li>'
                        for att in skipped
                    )
                    body_html += (
                        "<p>Часть вложений слишком велика для письма и не приложена — "
                        f"файлы доступны в приложении по ссылке:</p><ul>{html_links}</ul>"
                    )

            msg.set_content(body_text)
            if body_html:
                msg.add_alternative(body_html, subtype="html")
            for att in inline:
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
            # Порт 465 — implicit TLS (SMTPS); 587/2525 — STARTTLS. SMTP_TLS=true
            # включает шифрование соответствующим способом, иначе — открытое
            # соединение. Раньше use_tls=true на 587 ломал хендшейк
            # (SSL: WRONG_VERSION_NUMBER), из-за чего письма не отправлялись.
            implicit_tls = settings.smtp_tls and settings.smtp_port == 465
            start_tls = settings.smtp_tls and settings.smtp_port != 465
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                use_tls=implicit_tls,
                start_tls=start_tls,
                timeout=20,
            )
            return DeliveryResult(self.kind, DeliveryStatus.DELIVERED)
        except Exception as exc:  # noqa: BLE001 — гарантированный канал: помечаем для ретрая
            return DeliveryResult(self.kind, DeliveryStatus.FAILED, str(exc)[:300])
