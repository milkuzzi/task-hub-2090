"""DTO чата задачи (§4, task-collaboration)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class MessageIn(CamelModel):
    body: str = Field(min_length=1)


class MessageOut(CamelModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    body: str
    created_at: datetime


class MessageListOut(CamelModel):
    items: list[MessageOut]
    # Курсор для дозагрузки (created_at последнего сообщения), null — больше нет.
    next_after: datetime | None = None
