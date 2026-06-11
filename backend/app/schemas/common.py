"""Базовая модель DTO и общие выходные типы.

Формат провода — camelCase (зеркалит TS-контракт §13.6.4); имена полей в Python —
snake_case через alias_generator. FastAPI сериализует ответы by_alias по умолчанию.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.domain.enums import AttachKind, DueMode, TaskStatus


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UserRefOut(CamelModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_deleted: bool


class AttachmentOut(CamelModel):
    id: uuid.UUID
    kind: AttachKind
    filename: str | None = None
    size: int | None = None
    content_type: str | None = None
    url: str | None = None
    download_url: str | None = None


class ReportOut(CamelModel):
    text: str | None = None
    attachments: list[AttachmentOut] = []
    ready: bool = False
    ready_at: datetime | None = None
    updated_at: datetime | None = None


class TaskListItemOut(CamelModel):
    id: uuid.UUID
    seq_no: int
    code: str
    title: str
    deadline: datetime
    deadline_has_time: bool
    status: TaskStatus
    is_overdue: bool
    needs_reassignment: bool
    assignee: UserRefOut
    author: UserRefOut
    observers: list[UserRefOut] = []
    assignee_marked_ready: bool = False


class TaskDetailOut(TaskListItemOut):
    description: str | None = None
    attachments: list[AttachmentOut] = []
    report: ReportOut | None = None
    created_at: datetime
    updated_at: datetime


class TaskListResponse(CamelModel):
    items: list[TaskListItemOut]
    total: int
    page: int
    page_size: int


class OkResponse(CamelModel):
    ok: bool = True


def deadline_has_time(due_mode: DueMode) -> bool:
    return due_mode == DueMode.DATETIME
