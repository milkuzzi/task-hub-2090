"""Отчёт исполнителя и отметка готовности (§6, §13.5.4)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TaskContext
from app.core import errors
from app.core.clock import now
from app.domain import permissions
from app.domain.enums import Action, TaskStatus
from app.models import Task, TaskReport
from app.repositories import tasks_repo


async def _get_or_create_report(db: AsyncSession, task: Task, user_id) -> TaskReport:
    if task.report is None:
        report = TaskReport(task_id=task.id, updated_by=user_id)
        db.add(report)
        await db.flush()
        task.report = report
    return task.report


async def add_report(db: AsyncSession, ctx: TaskContext, *, text: str | None) -> Task:
    permissions.authorize(Action.ADD_REPORT, ctx.role, is_admin=ctx.user.is_admin)
    if ctx.task.status == TaskStatus.CANCELLED:
        raise errors.status_conflict()  # отчёт по отменённой задаче не принимается
    report = await _get_or_create_report(db, ctx.task, ctx.user.id)
    if text is not None:
        report.text = text
    report.updated_by = ctx.user.id
    await db.commit()
    return await tasks_repo.get_full(db, ctx.task.id)


async def mark_ready(db: AsyncSession, ctx: TaskContext, *, text: str | None) -> TaskReport:
    permissions.authorize(Action.MARK_READY, ctx.role, is_admin=ctx.user.is_admin)
    if ctx.task.status != TaskStatus.IN_PROGRESS:
        raise errors.status_conflict()  # отметка готовности — только по открытой задаче
    report = await _get_or_create_report(db, ctx.task, ctx.user.id)
    if report.ready_flag:
        raise errors.already_ready()
    report.ready_flag = True
    report.ready_at = now()
    report.updated_by = ctx.user.id
    if text is not None:
        report.text = text
    await db.commit()
    return report
