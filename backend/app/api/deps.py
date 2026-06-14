"""Серверные зависимости-гарды (§13.3.3, §13.3.5, §13.3.6).

`get_current_user` проверяет членство e-mail в реестре на КАЖДЫЙ запрос —
удалённый из реестра пользователь теряет доступ немедленно. Роль на задаче
вычисляется единой `get_task_context` (нельзя «забыть» проверку).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.security import decode_access_token
from app.db.session import get_db
from app.domain.enums import TaskRole
from app.domain.roles import role_of
from app.models import Task
from app.repositories import registry_repo, tasks_repo, users_repo

_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: uuid.UUID
    email: str
    is_admin: bool
    display_name: str


@dataclass
class TaskContext:
    task: Task
    user: CurrentUser
    role: TaskRole


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if creds is None or not creds.credentials:
        raise errors.unauthenticated()
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise errors.unauthenticated() from None
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise errors.unauthenticated() from None

    user = await users_repo.get_active_by_id(db, user_id)
    if user is None:
        raise errors.registry_access_revoked()
    # КЛЮЧЕВАЯ ПРОВЕРКА: e-mail всё ещё в реестре (§3 п.12)
    if not await registry_repo.is_listed(db, user.email):
        raise errors.registry_access_revoked()
    return CurrentUser(
        id=user.id, email=user.email, is_admin=user.is_admin, display_name=user.display_name
    )


async def require_admin(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    # Перепроверяем по БД, а не доверяем claim из JWT (§13.3.5).
    if not await users_repo.is_admin(db, user.id):
        raise errors.forbidden_admin()
    return user


async def get_task_context(
    task_id: uuid.UUID = Path(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskContext:
    task = await tasks_repo.get_full(db, task_id)
    if task is None:
        raise errors.task_not_found()
    role = role_of(
        user.id,
        author_id=task.author_id,
        assignee_ids=task.assignee_ids,
        observer_ids=task.observer_ids,
    )
    if role == TaskRole.NONE and not user.is_admin:
        # 404, а не 403 — не раскрываем существование чужой задачи (§13.5.2).
        # Администратор имеет доступ к любой задаче через override.
        raise errors.task_not_found()
    return TaskContext(task=task, user=user, role=role)
