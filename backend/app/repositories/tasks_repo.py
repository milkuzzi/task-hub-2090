"""Доступ к задачам: сквозной номер без дыр, 6-значный код, списки по ипостаси,
карточка с отношениями, удаление архива (§13.2.5, §13.2.6, §13.2.10)."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.enums import DueMode, TaskRole, TaskStatus
from app.models import Task, TaskObserver, User

_CODE6_RETRIES = 10


async def next_task_no(db: AsyncSession) -> int:
    """Сквозной номер без дыр: блокировка строки счётчика (§13.2.5)."""
    res = await db.execute(
        text("UPDATE counters SET value = value + 1 WHERE name = 'task_no' RETURNING value")
    )
    return int(res.scalar_one())


async def code6_taken(db: AsyncSession, code: int) -> bool:
    res = await db.execute(select(Task.id).where(Task.code6 == code))
    return res.first() is not None


async def create_task(
    db: AsyncSession,
    *,
    title: str,
    description: str | None,
    due_at: datetime,
    due_mode: DueMode,
    author_id: uuid.UUID,
    assignee_id: uuid.UUID,
) -> Task:
    """Создаёт задачу: сквозной номер + уникальный 6-значный код (повтор при коллизии)."""
    task_no = await next_task_no(db)
    for _ in range(_CODE6_RETRIES):
        code6 = secrets.randbelow(900_000) + 100_000  # 100000..999999
        if await code6_taken(db, code6):
            continue
        task = Task(
            task_no=task_no,
            code6=code6,
            title=title,
            description=description,
            due_at=due_at,
            due_mode=due_mode,
            author_id=author_id,
            assignee_id=assignee_id,
        )
        db.add(task)
        try:
            async with db.begin_nested():  # savepoint: гонку закрывает UNIQUE(code6)
                await db.flush()
            return task
        except IntegrityError:
            db.expunge(task)
            continue
    raise RuntimeError("CODE6_EXHAUSTED")


async def get_full(db: AsyncSession, task_id: uuid.UUID) -> Task | None:
    """Карточка задачи со всеми отношениями (eager-загрузка через модель)."""
    res = await db.execute(select(Task).where(Task.id == task_id))
    return res.unique().scalar_one_or_none()


async def get_by_code6(db: AsyncSession, code: int) -> Task | None:
    res = await db.execute(select(Task).where(Task.code6 == code))
    return res.unique().scalar_one_or_none()


def _apply_role_filter(stmt, role: TaskRole, user_id: uuid.UUID):
    if role == TaskRole.AUTHOR:
        return stmt.where(Task.author_id == user_id)
    if role == TaskRole.ASSIGNEE:
        return stmt.where(Task.assignee_id == user_id)
    if role == TaskRole.OBSERVER:
        return stmt.join(TaskObserver, TaskObserver.task_id == Task.id).where(
            TaskObserver.user_id == user_id
        )
    raise ValueError(f"unsupported role for listing: {role}")


_SORT_COLUMNS = {
    "deadline": Task.due_at,
    "status": Task.status,
    "title": Task.title,
    "seqNo": Task.task_no,
    "code": Task.code6,
    "createdAt": Task.created_at,
    "overdue": Task.is_overdue,
}


async def list_tasks(
    db: AsyncSession,
    *,
    role: TaskRole,
    user_id: uuid.UUID,
    status_filter: TaskStatus | None,
    sort: str | None,
    order: str,
    page: int,
    page_size: int,
) -> tuple[list[Task], int]:
    base = select(Task)
    base = _apply_role_filter(base, role, user_id)
    if status_filter is not None:
        base = base.where(Task.status == status_filter)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    desc = order.lower() == "desc"
    if sort in _SORT_COLUMNS:
        col = _SORT_COLUMNS[sort]
        base = base.order_by(col.desc() if desc else col.asc(), Task.due_at.asc())
    elif sort in ("assignee", "author"):
        u = aliased(User)
        join_col = Task.assignee_id if sort == "assignee" else Task.author_id
        base = base.join(u, u.id == join_col).order_by(
            u.display_name.desc() if desc else u.display_name.asc(), Task.due_at.asc()
        )
    else:
        # по умолчанию: открытые выше закрытых, затем ближайший срок выше (§8)
        base = base.order_by(
            (Task.status == TaskStatus.IN_PROGRESS).desc(), Task.due_at.asc()
        )

    base = base.offset((page - 1) * page_size).limit(page_size)
    rows = list((await db.execute(base)).unique().scalars().all())
    return rows, total


async def delete_task(db: AsyncSession, task: Task) -> None:
    await db.delete(task)
    await db.flush()


# --- Поддержка удаления пользователя (§13.2.9) ---


async def collect_author_file_paths(db: AsyncSession, author_id: uuid.UUID) -> list[str]:
    """Пути файлов всех вложений в задачах, где пользователь — постановщик."""
    task_files = await db.execute(
        text(
            "SELECT ta.file_path FROM task_attachments ta "
            "JOIN tasks t ON t.id = ta.task_id "
            "WHERE t.author_id = :uid AND ta.file_path IS NOT NULL"
        ),
        {"uid": author_id},
    )
    report_files = await db.execute(
        text(
            "SELECT ra.file_path FROM report_attachments ra "
            "JOIN task_reports tr ON tr.task_id = ra.task_id "
            "JOIN tasks t ON t.id = tr.task_id "
            "WHERE t.author_id = :uid AND ra.file_path IS NOT NULL"
        ),
        {"uid": author_id},
    )
    return [r[0] for r in task_files.all()] + [r[0] for r in report_files.all()]


async def delete_authored_tasks(db: AsyncSession, author_id: uuid.UUID) -> int:
    """Hard-delete задач пользователя-постановщика (каскад снимет детей)."""
    res = await db.execute(
        select(Task).where(Task.author_id == author_id)
    )
    tasks = list(res.unique().scalars().all())
    for task in tasks:
        await db.delete(task)
    await db.flush()
    return len(tasks)


async def flag_foreign_for_reassignment(
    db: AsyncSession, assignee_id: uuid.UUID
) -> int:
    """Чужие задачи, где удаляемый — исполнитель, помечаем needs_reassignment (§13.5.4)."""
    res = await db.execute(
        update(Task)
        .where(Task.assignee_id == assignee_id, Task.author_id != assignee_id)
        .values(needs_reassignment=True)
        .returning(Task.id)
    )
    await db.flush()
    return len(res.all())


async def anonymize_observer(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(TaskObserver)
        .where(TaskObserver.user_id == user_id)
        .values(display_name="Пользователь удалён")
    )
    await db.flush()


async def iter_active_tasks_for_notifications(
    db: AsyncSession, *, recent_since: datetime | None = None
) -> Sequence[Task]:
    """Задачи для суточного прогона: открытые + недавно созданные (страховка
    по событию №1). Без `recent_since` — все задачи (обратная совместимость)."""
    stmt = select(Task)
    if recent_since is not None:
        stmt = stmt.where(
            or_(Task.status == TaskStatus.IN_PROGRESS, Task.created_at >= recent_since)
        )
    stmt = stmt.order_by(Task.task_no.asc())
    res = await db.execute(stmt)
    return list(res.unique().scalars().all())
