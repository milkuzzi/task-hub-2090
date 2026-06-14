"""Чат задачи: история и отправка сообщений + WS-доставка участникам (§4).

Доступ — строго по роли (POST_MESSAGE: автор/исполнитель/наблюдатель, админ через
override). Запись идёт через REST (валидация/права), WS — канал доставки. После
коммита: рассылка `chat` всем участникам онлайн + создание/пуш уведомлений
исполнителям (кроме автора сообщения).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TaskContext
from app.core import errors
from app.core.config import settings
from app.domain import permissions
from app.domain.enums import Action
from app.models import TaskMessage
from app.realtime.manager import manager
from app.repositories import messages_repo
from app.schemas.chat import MessageListOut, MessageOut
from app.services import notification_center


def _author_name(msg: TaskMessage) -> str:
    if msg.author is None or msg.author.is_deleted:
        return "Пользователь удалён"
    return msg.author.display_name


def _message_out(msg: TaskMessage) -> MessageOut:
    return MessageOut(
        id=msg.id,
        author_id=msg.author_id,
        author_name=_author_name(msg),
        body=msg.body,
        created_at=msg.created_at,
    )


def _participant_ids(ctx: TaskContext) -> list[uuid.UUID]:
    """Все, кто видит чат: постановщик + исполнители + наблюдатели (уникально)."""
    ids = [ctx.task.author_id, *ctx.task.assignee_ids, *ctx.task.observer_ids]
    return list(dict.fromkeys(ids))


async def list_messages(
    db: AsyncSession, ctx: TaskContext, *, after: datetime | None, limit: int
) -> MessageListOut:
    """История сообщений (хронологически). `after` — keyset-курсор по created_at.

    Просмотр чата доступен любому участнику (роль ≠ NONE) — гарантируется
    `get_task_context`, который уже отсёк посторонних (404).
    """
    permissions.authorize(Action.VIEW, ctx.role, is_admin=ctx.user.is_admin)
    limit = max(1, min(limit, messages_repo.MAX_PAGE_SIZE))
    # Публичный курсор — только createdAt: семантика «строго позже этой метки».
    # Берём максимальный UUID в id-компоненте, чтобы equality-ветка keyset не
    # возвращала само граничное сообщение (в проде метки времени различны).
    cursor = (after, uuid.UUID(int=(1 << 128) - 1)) if after is not None else None
    rows = await messages_repo.list_messages(db, ctx.task.id, after=cursor, limit=limit)
    items = [_message_out(m) for m in rows]
    next_after = rows[-1].created_at if len(rows) == limit and rows else None
    return MessageListOut(items=items, next_after=next_after)


async def post_message(db: AsyncSession, ctx: TaskContext, body: str) -> MessageOut:
    permissions.authorize(Action.POST_MESSAGE, ctx.role, is_admin=ctx.user.is_admin)

    text = body.strip()
    if not text:
        raise errors.validation_error(
            [{"field": "body", "message": "Сообщение не может быть пустым."}]
        )
    if len(text) > settings.max_message_len:
        raise errors.validation_error(
            [
                {
                    "field": "body",
                    "message": f"Сообщение длиннее {settings.max_message_len} символов.",
                }
            ]
        )

    msg = await messages_repo.create_message(
        db, task_id=ctx.task.id, author_id=ctx.user.id, body=text
    )
    notifs = await notification_center.build_chat_notifications(
        db, task=ctx.task, message_id=msg.id, author_id=ctx.user.id, text=text
    )
    await db.commit()

    # Перечитываем с автором (join) для актуального имени и created_at.
    saved = await messages_repo.get_by_id(db, msg.id)
    out = _message_out(saved if saved is not None else msg)

    # Доставка после коммита: чат — всем участникам, уведомления — исполнителям.
    await manager.send_to_users(
        _participant_ids(ctx),
        {
            "type": "chat",
            "taskId": str(ctx.task.id),
            "message": out.model_dump(by_alias=True, mode="json"),
        },
    )
    await notification_center.push_notifications(notifs)
    return out
