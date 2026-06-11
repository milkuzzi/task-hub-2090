"""DTO задач: создание, изменение, смена статуса (§13.5.4).

Инварианты первого барьера (Pydantic): обязательное название, ровно один
`assignee_id` (скаляр), ≤5 наблюдателей. Доменные проверки — обязательны сверх этого.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from app.domain.enums import DueMode, TaskStatus
from app.schemas.common import CamelModel


class TaskCreateIn(CamelModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20000)
    due_at: datetime
    due_mode: DueMode = DueMode.DATETIME
    assignee_id: uuid.UUID
    observer_ids: list[uuid.UUID] = Field(default_factory=list, max_length=5)
    links: list[str] = Field(default_factory=list, max_length=50)


class TaskUpdateIn(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20000)
    due_at: datetime | None = None
    due_mode: DueMode | None = None
    assignee_id: uuid.UUID | None = None
    observer_ids: list[uuid.UUID] | None = Field(default=None, max_length=5)


class StatusIn(CamelModel):
    status: TaskStatus
