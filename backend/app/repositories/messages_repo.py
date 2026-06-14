"""Доступ к сообщениям чата задачи (§4, design.md «task_messages»).

Пагинация — keyset по (created_at, id): курсор `after` отдаёт следующую страницу
в хронологическом порядке без OFFSET (стабильно при дозагрузке).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TaskMessage

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


async def create_message(
    db: AsyncSession, *, task_id: uuid.UUID, author_id: uuid.UUID, body: str
) -> TaskMessage:
    msg = TaskMessage(task_id=task_id, author_id=author_id, body=body)
    db.add(msg)
    await db.flush()
    return msg


async def get_by_id(db: AsyncSession, message_id: uuid.UUID) -> TaskMessage | None:
    res = await db.execute(select(TaskMessage).where(TaskMessage.id == message_id))
    return res.unique().scalar_one_or_none()


async def list_messages(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    after: tuple[datetime, uuid.UUID] | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[TaskMessage]:
    """Сообщения задачи в хронологическом порядке.

    `after=(created_at, id)` — вернуть строго более поздние сообщения (keyset).
    """
    stmt = select(TaskMessage).where(TaskMessage.task_id == task_id)
    if after is not None:
        cursor_at, cursor_id = after
        stmt = stmt.where(
            or_(
                TaskMessage.created_at > cursor_at,
                and_(TaskMessage.created_at == cursor_at, TaskMessage.id > cursor_id),
            )
        )
    stmt = stmt.order_by(TaskMessage.created_at.asc(), TaskMessage.id.asc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.unique().scalars().all())


async def list_recent(
    db: AsyncSession, task_id: uuid.UUID, *, limit: int = DEFAULT_PAGE_SIZE
) -> Sequence[TaskMessage]:
    """Последние сообщения задачи (для первичной загрузки ленты)."""
    stmt = (
        select(TaskMessage)
        .where(TaskMessage.task_id == task_id)
        .order_by(TaskMessage.created_at.desc(), TaskMessage.id.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    rows = list(res.unique().scalars().all())
    rows.reverse()  # отдаём в хронологическом порядке
    return rows
