"""Журнал уведомлений: бронь-перед-отправкой и фиксация результатов (§13.4.3, §13.4.5).

Идемпотентность — через INSERT ... ON CONFLICT DO NOTHING по частичным уникальным
индексам, а не через предварительную проверку «есть ли запись». Перезапуск воркера
в середине прогона не порождает дублей.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotifyEvent
from app.models import NotificationLog


async def reserve(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    event_type: NotifyEvent,
    recipient_id: uuid.UUID,
    due_version: int | None,
    run_date: date | None,
) -> bool:
    """Вставляет «бронь» до отправки. True → новая запись (отправляем), False → уже было."""
    values = {
        "task_id": task_id,
        "event_type": event_type.value,
        "recipient_id": recipient_id,
        "due_version": due_version,
        "run_date": run_date,
        "email_status": "skipped",
        "max_status": "skipped",
    }
    stmt = pg_insert(NotificationLog).values(**values)
    if event_type == NotifyEvent.ASSIGNED:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["task_id", "event_type", "recipient_id"],
            index_where=text("event_type = 'assigned'"),
        )
    else:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["task_id", "event_type", "recipient_id", "due_version", "run_date"],
            index_where=text("run_date IS NOT NULL"),
        )
    stmt = stmt.returning(NotificationLog.id)
    res = await db.execute(stmt)
    return res.first() is not None


async def record_results(
    db: AsyncSession,
    *,
    task_id: uuid.UUID,
    event_type: NotifyEvent,
    recipient_id: uuid.UUID,
    due_version: int | None,
    run_date: date | None,
    email_status: str,
    max_status: str,
    detail: str | None,
) -> None:
    conds = [
        NotificationLog.task_id == task_id,
        NotificationLog.event_type == event_type.value,
        NotificationLog.recipient_id == recipient_id,
    ]
    if run_date is None:
        conds.append(NotificationLog.run_date.is_(None))
    else:
        conds.append(NotificationLog.run_date == run_date)
    if due_version is None:
        conds.append(NotificationLog.due_version.is_(None))
    else:
        conds.append(NotificationLog.due_version == due_version)

    await db.execute(
        update(NotificationLog)
        .where(and_(*conds))
        .values(email_status=email_status, max_status=max_status, detail=detail)
    )
    await db.flush()


async def list_failed_email(db: AsyncSession, run_date: date) -> list[NotificationLog]:
    res = await db.execute(
        select(NotificationLog).where(
            NotificationLog.email_status == "failed", NotificationLog.run_date == run_date
        )
    )
    return list(res.scalars().all())


async def count_for_task(db: AsyncSession, task_id: uuid.UUID) -> int:
    res = await db.execute(
        select(NotificationLog.id).where(NotificationLog.task_id == task_id)
    )
    return len(res.all())
