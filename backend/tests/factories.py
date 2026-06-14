"""Фабрики данных и хелперы аутентификации для тестов."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.clock import now
from app.core.security import create_access_token, hash_password
from app.domain.enums import DueMode
from app.models import EmailRegistry, Task, User
from app.schemas.tasks import TaskCreateIn
from app.services import task_service

DEFAULT_PASSWORD = "password123"


async def make_user(
    db: AsyncSession,
    email: str,
    *,
    is_admin: bool = False,
    display_name: str | None = None,
    max_contact: str | None = None,
) -> User:
    db.add(EmailRegistry(email=email, is_admin=is_admin, max_user_id=max_contact))
    user = User(
        email=email,
        password_hash=hash_password(DEFAULT_PASSWORD),
        display_name=display_name or email.split("@")[0],
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    return user


def current_of(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id, email=user.email, is_admin=user.is_admin, display_name=user.display_name
    )


def auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user_id=user.id, email=user.email, is_admin=user.is_admin)
    return {"Authorization": f"Bearer {token}"}


def create_task_form(payload: dict) -> dict[str, str]:
    """Поля multipart-формы для `POST /tasks`: тело задачи JSON-строкой в `payload`.

    Контракт §6: `payload` (JSON) + ноль или более `files`.
    """
    return {"payload": json.dumps(payload)}


async def make_task(
    db: AsyncSession,
    author: User,
    assignee: User,
    observers: Sequence[User] = (),
    *,
    assignees: Sequence[User] | None = None,
    title: str = "Задача",
    due_at: datetime | None = None,
    due_mode: DueMode = DueMode.DATETIME,
    links: list[str] | None = None,
) -> Task:
    # Совместимость: позиционный `assignee` — основной исполнитель; через
    # `assignees` можно задать несколько (тогда `assignee` игнорируется).
    assignee_users = list(assignees) if assignees is not None else [assignee]
    data = TaskCreateIn(
        title=title,
        due_at=due_at or (now() + timedelta(days=2)),
        due_mode=due_mode,
        assignee_ids=[u.id for u in assignee_users],
        observer_ids=[o.id for o in observers],
        links=links or [],
    )
    return await task_service.create_task(db, current_of(author), data)
