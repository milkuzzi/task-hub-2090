"""Сценарии задач: создание, изменение, статус, удаление, поиск, списки (§13.3.6)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, TaskContext
from app.core import errors
from app.core.clock import end_of_day, now, to_org_tz
from app.domain import invariants, permissions
from app.domain import status as status_domain
from app.domain.enums import Action, AttachKind, DueMode, TaskRole, TaskStatus
from app.domain.overdue import due_moment
from app.domain.roles import role_of
from app.models import Task, TaskAttachment, TaskObserver, User
from app.repositories import registry_repo, tasks_repo, users_repo
from app.schemas.tasks import TaskCreateIn, TaskUpdateIn

_ROLE_MAP = {
    "author": TaskRole.AUTHOR,
    "assignee": TaskRole.ASSIGNEE,
    "observer": TaskRole.OBSERVER,
}


def _normalize_due(due_at: datetime, due_mode: DueMode) -> datetime:
    due_at = to_org_tz(due_at)
    if due_mode == DueMode.DATE:
        return end_of_day(due_at.date())  # конец дня-срока; просрочка — со след. суток
    return due_at


def _validate_link(url: str) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise errors.validation_error([{"field": "links", "message": "Ссылка должна быть http(s)."}])
    return url


async def _require_active_listed(db: AsyncSession, user_id: uuid.UUID, field: str) -> User:
    user = await users_repo.get_active_by_id(db, user_id)
    if user is None or not await registry_repo.is_listed(db, user.email):
        raise errors.validation_error(
            [{"field": field, "message": "Пользователь не найден или не имеет доступа."}]
        )
    return user


async def _resolve_observers(
    db: AsyncSession, observer_ids: Sequence[uuid.UUID]
) -> list[User]:
    users = await users_repo.get_active_by_ids(db, observer_ids)
    found = {u.id for u in users}
    missing = [oid for oid in observer_ids if oid not in found]
    if missing:
        raise errors.validation_error(
            [{"field": "observers", "message": "Наблюдатель не найден или не имеет доступа."}]
        )
    for u in users:
        if not await registry_repo.is_listed(db, u.email):
            raise errors.validation_error(
                [{"field": "observers", "message": "Наблюдатель не имеет доступа к сервису."}]
            )
    # сохраняем исходный порядок
    by_id = {u.id: u for u in users}
    return [by_id[oid] for oid in observer_ids if oid in by_id]


async def create_task(db: AsyncSession, current: CurrentUser, data: TaskCreateIn) -> Task:
    title = invariants.validate_title(data.title)
    assignee_id = invariants.validate_assignee(data.assignee_id)
    observer_ids = invariants.validate_observers(
        data.observer_ids, assignee_id=assignee_id, author_id=current.id
    )
    await _require_active_listed(db, assignee_id, "assignee_id")
    obs_users = await _resolve_observers(db, observer_ids)

    task = await tasks_repo.create_task(
        db,
        title=title,
        description=data.description,
        due_at=_normalize_due(data.due_at, data.due_mode),
        due_mode=data.due_mode,
        author_id=current.id,
        assignee_id=assignee_id,
    )
    for u in obs_users:
        db.add(TaskObserver(task_id=task.id, user_id=u.id, display_name=u.display_name))
    for url in data.links:
        db.add(TaskAttachment(task_id=task.id, kind=AttachKind.URL, url=_validate_link(url)))
    await db.commit()
    return await tasks_repo.get_full(db, task.id)


def _on_due_changed(task: Task) -> None:
    task.due_version += 1
    moment = due_moment(task.due_at, task.due_mode)
    if now() < moment:
        # новый срок ещё не наступил → снимаем факт просрочки (§13.4.4)
        task.is_overdue = False
        task.overdue_since = None


async def update_task(db: AsyncSession, ctx: TaskContext, data: TaskUpdateIn) -> Task:
    permissions.authorize(Action.EDIT_FIELDS, ctx.role)
    task = ctx.task

    if data.title is not None:
        task.title = invariants.validate_title(data.title)
    if data.description is not None:
        task.description = data.description

    due_changed = False
    new_due_at = task.due_at
    new_due_mode = task.due_mode
    if data.due_mode is not None:
        new_due_mode = data.due_mode
        due_changed = True
    if data.due_at is not None:
        new_due_at = data.due_at
        due_changed = True
    if due_changed:
        task.due_at = _normalize_due(new_due_at, new_due_mode)
        task.due_mode = new_due_mode
        _on_due_changed(task)

    if data.assignee_id is not None:
        invariants.validate_assignee(data.assignee_id)
        new_assignee = await _require_active_listed(db, data.assignee_id, "assignee_id")
        task.assignee = new_assignee  # обновляем и FK, и relationship (иначе кэш устаревает)
        task.needs_reassignment = False  # переназначение снимает флаг

    if data.observer_ids is not None:
        observer_ids = invariants.validate_observers(
            data.observer_ids, assignee_id=task.assignee_id, author_id=task.author_id
        )
        obs_users = await _resolve_observers(db, observer_ids)
        task.observers.clear()
        await db.flush()
        for u in obs_users:
            task.observers.append(TaskObserver(user_id=u.id, display_name=u.display_name))

    await db.commit()
    return await tasks_repo.get_full(db, task.id)


async def change_status(db: AsyncSession, ctx: TaskContext, new_status: TaskStatus) -> Task:
    permissions.authorize(Action.CHANGE_STATUS, ctx.role)
    status_domain.validate_transition(ctx.task.status, new_status)
    ctx.task.status = new_status  # флаг is_overdue не трогаем (§5)
    await db.commit()
    return await tasks_repo.get_full(db, ctx.task.id)


async def delete_task(db: AsyncSession, ctx: TaskContext) -> None:
    permissions.authorize(Action.DELETE_TASK, ctx.role)
    from app.storage.base import get_storage

    task_id = ctx.task.id
    paths = [a.file_path for a in ctx.task.attachments if a.file_path]
    if ctx.task.report is not None:
        paths += [a.file_path for a in ctx.task.report.attachments if a.file_path]
    await tasks_repo.delete_task(db, ctx.task)
    await db.commit()
    get_storage().delete_task_dir(task_id)


async def search_by_code(db: AsyncSession, current: CurrentUser, code: int) -> Task:
    task = await tasks_repo.get_by_code6(db, code)
    if task is None:
        raise errors.task_not_found()
    role = role_of(
        current.id,
        author_id=task.author_id,
        assignee_id=task.assignee_id,
        observer_ids=task.observer_ids,
    )
    if role == TaskRole.NONE:
        raise errors.task_not_found()
    return task


async def list_tasks(
    db: AsyncSession,
    current: CurrentUser,
    *,
    role: str,
    status_filter: TaskStatus | None,
    sort: str | None,
    order: str,
    page: int,
    page_size: int,
) -> tuple[list[Task], int]:
    task_role = _ROLE_MAP.get(role)
    if task_role is None:
        raise errors.bad_request("Неизвестная ипостась.")
    return await tasks_repo.list_tasks(
        db,
        role=task_role,
        user_id=current.id,
        status_filter=status_filter,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
