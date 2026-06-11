"""Вложения задачи и отчёта: загрузка с потоковой проверкой размера, безопасная
раздача только через эндпойнт с проверкой прав, удаление (§13.5.6)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TaskContext
from app.core import errors
from app.core.config import settings
from app.domain import permissions
from app.domain.enums import Action, AttachKind
from app.models import ReportAttachment, TaskAttachment, TaskReport
from app.storage.base import get_storage

_CHUNK = 1024 * 1024


@dataclass
class DownloadTarget:
    kind: AttachKind
    path: str | None
    url: str | None
    filename: str | None
    mime_type: str | None


async def _read_limited(upload: UploadFile) -> bytes:
    max_bytes = settings.max_file_size_mb_upload * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:  # обрываем поток, не буферизуя гигантский файл
            raise errors.file_too_large()
        chunks.append(chunk)
    return b"".join(chunks)


async def _count_files(db: AsyncSession, model, task_id: uuid.UUID) -> int:
    res = await db.execute(
        select(func.count())
        .select_from(model)
        .where(model.task_id == task_id, model.kind == AttachKind.FILE)
    )
    return res.scalar_one()


async def _ensure_report(db: AsyncSession, ctx: TaskContext) -> TaskReport:
    if ctx.task.report is None:
        report = TaskReport(task_id=ctx.task.id, updated_by=ctx.user.id)
        db.add(report)
        await db.flush()
        ctx.task.report = report
    return ctx.task.report


async def add_task_file(db: AsyncSession, ctx: TaskContext, upload: UploadFile) -> TaskAttachment:
    permissions.authorize(Action.ADD_ATTACHMENT_TASK, ctx.role)
    if not upload.filename or not upload.filename.strip():
        raise errors.unsupported_filename()
    if await _count_files(db, TaskAttachment, ctx.task.id) >= settings.max_files_per_task:
        raise errors.attachments_limit()
    data = await _read_limited(upload)
    stored = get_storage().save(ctx.task.id, data)
    att = TaskAttachment(
        task_id=ctx.task.id,
        kind=AttachKind.FILE,
        file_path=stored.stored_key,
        original_name=upload.filename,
        mime_type=upload.content_type,
        size_bytes=stored.size,
        uploaded_by=ctx.user.id,
    )
    db.add(att)
    await db.commit()
    return att


async def add_task_link(db: AsyncSession, ctx: TaskContext, url: str) -> TaskAttachment:
    permissions.authorize(Action.ADD_ATTACHMENT_TASK, ctx.role)
    _validate_link(url)
    att = TaskAttachment(task_id=ctx.task.id, kind=AttachKind.URL, url=url, uploaded_by=ctx.user.id)
    db.add(att)
    await db.commit()
    return att


async def add_report_file(db: AsyncSession, ctx: TaskContext, upload: UploadFile) -> ReportAttachment:
    permissions.authorize(Action.ADD_REPORT, ctx.role)
    if not upload.filename or not upload.filename.strip():
        raise errors.unsupported_filename()
    await _ensure_report(db, ctx)
    if await _count_files(db, ReportAttachment, ctx.task.id) >= settings.max_files_per_report:
        raise errors.attachments_limit()
    data = await _read_limited(upload)
    stored = get_storage().save(ctx.task.id, data)
    att = ReportAttachment(
        task_id=ctx.task.id,
        kind=AttachKind.FILE,
        file_path=stored.stored_key,
        original_name=upload.filename,
        mime_type=upload.content_type,
        size_bytes=stored.size,
        uploaded_by=ctx.user.id,
    )
    db.add(att)
    await db.commit()
    return att


async def add_report_link(db: AsyncSession, ctx: TaskContext, url: str) -> ReportAttachment:
    permissions.authorize(Action.ADD_REPORT, ctx.role)
    _validate_link(url)
    await _ensure_report(db, ctx)
    att = ReportAttachment(
        task_id=ctx.task.id, kind=AttachKind.URL, url=url, uploaded_by=ctx.user.id
    )
    db.add(att)
    await db.commit()
    return att


async def get_download(db: AsyncSession, ctx: TaskContext, att_id: uuid.UUID) -> DownloadTarget:
    """Любой с ролью на задаче может скачать вложение (§13.5.6)."""
    res = await db.execute(
        select(TaskAttachment).where(
            TaskAttachment.id == att_id, TaskAttachment.task_id == ctx.task.id
        )
    )
    att: TaskAttachment | ReportAttachment | None = res.scalar_one_or_none()
    if att is None:
        res = await db.execute(
            select(ReportAttachment).where(
                ReportAttachment.id == att_id, ReportAttachment.task_id == ctx.task.id
            )
        )
        att = res.scalar_one_or_none()
    if att is None:
        raise errors.attachment_not_found()
    return DownloadTarget(
        kind=att.kind,
        path=att.file_path,
        url=att.url,
        filename=att.original_name,
        mime_type=att.mime_type,
    )


async def delete_attachment(db: AsyncSession, ctx: TaskContext, att_id: uuid.UUID) -> None:
    storage = get_storage()
    res = await db.execute(
        select(TaskAttachment).where(
            TaskAttachment.id == att_id, TaskAttachment.task_id == ctx.task.id
        )
    )
    task_att = res.scalar_one_or_none()
    if task_att is not None:
        permissions.authorize(Action.ADD_ATTACHMENT_TASK, ctx.role)  # task-вложение → постановщик
        if task_att.file_path:
            storage.delete(task_att.file_path)
        await db.delete(task_att)
        await db.commit()
        return

    res = await db.execute(
        select(ReportAttachment).where(
            ReportAttachment.id == att_id, ReportAttachment.task_id == ctx.task.id
        )
    )
    report_att = res.scalar_one_or_none()
    if report_att is None:
        raise errors.attachment_not_found()
    permissions.authorize(Action.ADD_REPORT, ctx.role)  # report-вложение → исполнитель
    if report_att.file_path:
        storage.delete(report_att.file_path)
    await db.delete(report_att)
    await db.commit()


def _validate_link(url: str) -> None:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise errors.validation_error([{"field": "url", "message": "Ссылка должна быть http(s)."}])
