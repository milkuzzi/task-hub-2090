"""Роутер on-site уведомлений (§6, task-collaboration).

Список, счётчик непрочитанных и пометка прочитанными. Доступ — только к своим
уведомлениям (по `current_user.id`); чужие недоступны.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.schemas.notifications import (
    MarkReadIn,
    MarkReadOut,
    NotificationListOut,
    UnreadCountOut,
)
from app.services import notification_center

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    unread: bool = Query(default=False),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, unread_total = await notification_center.list_notifications(
        db, user.id, unread_only=unread
    )
    return NotificationListOut(
        items=[notification_center.to_out(n) for n in items], unread=unread_total
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return UnreadCountOut(unread=await notification_center.unread_count(db, user.id))


@router.post("/read", response_model=MarkReadOut)
async def mark_read(
    body: MarkReadIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    marked, unread = await notification_center.mark_read(
        db, user.id, ids=body.ids, task_id=body.task_id
    )
    return MarkReadOut(marked=marked, unread=unread)
