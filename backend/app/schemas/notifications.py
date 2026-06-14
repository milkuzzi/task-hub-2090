"""DTO on-site уведомлений (§6, task-collaboration)."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import CamelModel


class NotificationOut(CamelModel):
    id: uuid.UUID
    kind: str
    text: str
    task_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    is_read: bool
    created_at: datetime


class NotificationListOut(CamelModel):
    items: list[NotificationOut]
    unread: int


class UnreadCountOut(CamelModel):
    unread: int


class MarkReadIn(CamelModel):
    # Пустой/отсутствующий список — пометить все непрочитанные пользователя.
    ids: list[uuid.UUID] | None = None
    # Если задан — пометить прочитанными уведомления по конкретной задаче
    # (используется фронтом при открытии карточки задачи).
    task_id: uuid.UUID | None = None


class MarkReadOut(CamelModel):
    marked: int
    unread: int
