"""On-site уведомления: создание, выборка, счётчик, прочтение + WS-доставка.

Канал отдельный от e-mail/MAX-напоминаний планировщика (Req 6.1): сюда попадают
события чата (`chat_message`) и возврата на доработку (`task_rework`). Создание
строк — в транзакции вызывающего сервиса; WS-пуш — ПОСЛЕ коммита (иначе клиент
получит уведомление о ещё не зафиксированных данных).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Notification, Task
from app.realtime.manager import manager
from app.repositories import notifications_repo
from app.schemas.notifications import NotificationOut

KIND_CHAT_MESSAGE = "chat_message"
KIND_TASK_REWORK = "task_rework"


def to_out(notif: Notification) -> NotificationOut:
    return NotificationOut.model_validate(notif)


def _payload(notif: Notification) -> dict:
    return {
        "type": "notification",
        "notification": to_out(notif).model_dump(by_alias=True, mode="json"),
    }


async def push_notifications(notifs: Sequence[Notification]) -> None:
    """Шлёт каждому адресату его уведомление по WS (после коммита)."""
    for notif in notifs:
        await manager.send_to_users([notif.user_id], _payload(notif))


async def build_chat_notifications(
    db: AsyncSession,
    *,
    task: Task,
    message_id: uuid.UUID,
    author_id: uuid.UUID,
    text: str,
) -> list[Notification]:
    """Создаёт уведомления исполнителям задачи, КРОМЕ автора сообщения (Req 6.6).

    Постановщик-исполнитель тоже исключается, если он автор сообщения.
    """
    recipients = [uid for uid in dict.fromkeys(task.assignee_ids) if uid != author_id]
    created: list[Notification] = []
    for uid in recipients:
        created.append(
            await notifications_repo.create(
                db,
                user_id=uid,
                kind=KIND_CHAT_MESSAGE,
                text=text,
                task_id=task.id,
                message_id=message_id,
            )
        )
    return created


async def build_rework_notifications(
    db: AsyncSession, task: Task
) -> list[Notification]:
    """Создаёт уведомления о возврате на доработку всем исполнителям (Req 6)."""
    text = f"Задача №{task.task_no} возвращена на доработку."
    created: list[Notification] = []
    for uid in dict.fromkeys(task.assignee_ids):
        created.append(
            await notifications_repo.create(
                db,
                user_id=uid,
                kind=KIND_TASK_REWORK,
                text=text,
                task_id=task.id,
            )
        )
    return created


# --- Сценарии для роутера уведомлений ---


async def list_notifications(
    db: AsyncSession, user_id: uuid.UUID, *, unread_only: bool
) -> tuple[list[Notification], int]:
    items = list(await notifications_repo.list_for_user(db, user_id, unread_only=unread_only))
    unread = await notifications_repo.unread_count(db, user_id)
    return items, unread


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return await notifications_repo.unread_count(db, user_id)


async def mark_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    ids: Sequence[uuid.UUID] | None,
    task_id: uuid.UUID | None = None,
) -> tuple[int, int]:
    if task_id is not None:
        marked = await notifications_repo.mark_read_for_task(db, user_id, task_id)
    else:
        marked = await notifications_repo.mark_read(db, user_id, ids=ids)
    await db.commit()
    unread = await notifications_repo.unread_count(db, user_id)
    return marked, unread
