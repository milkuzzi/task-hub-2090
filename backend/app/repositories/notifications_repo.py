"""Доступ к on-site уведомлениям (§6, design.md «notifications»)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification


async def create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    kind: str,
    text: str,
    task_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        kind=kind,
        text=text,
        task_id=task_id,
        message_id=message_id,
    )
    db.add(notif)
    await db.flush()
    return notif


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 100
) -> Sequence[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    res = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return int(res.scalar_one())


async def mark_read(
    db: AsyncSession, user_id: uuid.UUID, *, ids: Sequence[uuid.UUID] | None = None
) -> int:
    """Помечает уведомления прочитанными. `ids=None`/пустой — все непрочитанные.

    Идемпотентно: повторная пометка уже прочитанных строк ничего не меняет
    (фильтр `is_read=false`), счётчик непрочитанных не уходит ниже 0.
    """
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(list(ids)))
    res = await db.execute(stmt)
    await db.flush()
    return int(res.rowcount or 0)


async def mark_read_for_task(
    db: AsyncSession, user_id: uuid.UUID, task_id: uuid.UUID
) -> int:
    """Помечает прочитанными уведомления пользователя по конкретной задаче."""
    res = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.task_id == task_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.flush()
    return int(res.rowcount or 0)
