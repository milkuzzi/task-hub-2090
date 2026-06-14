"""Вложения задачи и отчёта: загрузка с потоковой проверкой размера, безопасная
раздача только через эндпойнт с проверкой прав, удаление (§13.5.6)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
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


@dataclass
class PreparedFile:
    """Прочитанный и проверенный (но ещё не сохранённый) файл-вложение."""

    filename: str
    content_type: str | None
    data: bytes


async def _read_limited(upload: UploadFile) -> bytes:
    return await read_upload_bounded(
        upload,
        max_bytes=settings.max_file_size_mb_upload * 1024 * 1024,
        too_large=errors.file_too_large,
    )


async def read_upload_bounded(
    upload: UploadFile,
    *,
    max_bytes: int,
    too_large: Callable[[], errors.AppError],
) -> bytes:
    """Потоковое чтение загрузки с ограничением размера (переиспользуемо).

    Читает файл чанками и обрывает поток, как только превышен `max_bytes` — без
    буферизации гигантского тела в памяти. При превышении бросает доменную ошибку
    `too_large()`. Пустой файл отклоняется как ошибка валидации.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:  # обрываем поток, не буферизуя гигантский файл
            raise too_large()
        chunks.append(chunk)
    data = b"".join(chunks)
    if not data:  # пустой файл — нечего хранить
        raise errors.validation_error([{"field": "file", "message": "Файл пустой."}])
    return data


async def _count_files(db: AsyncSession, model, task_id: uuid.UUID) -> int:
    res = await db.execute(
        select(func.count())
        .select_from(model)
        .where(model.task_id == task_id, model.kind == AttachKind.FILE)
    )
    return res.scalar_one()


async def _total_file_bytes(db: AsyncSession, task_id: uuid.UUID) -> int:
    """Суммарный размер всех файловых вложений задачи (вложения задачи + отчёта)."""
    total = 0
    for model in (TaskAttachment, ReportAttachment):
        res = await db.execute(
            select(func.coalesce(func.sum(model.size_bytes), 0)).where(
                model.task_id == task_id, model.kind == AttachKind.FILE
            )
        )
        total += int(res.scalar_one() or 0)
    return total


async def _ensure_total_within_limit(
    db: AsyncSession, task_id: uuid.UUID, new_size: int
) -> None:
    """Отклоняем загрузку, если суммарный размер файлов задачи превысит лимит (§M3)."""
    max_total = settings.max_task_total_mb * 1024 * 1024
    existing = await _total_file_bytes(db, task_id)
    if existing + new_size > max_total:
        raise errors.task_total_size_limit()


async def _ensure_report(db: AsyncSession, ctx: TaskContext) -> TaskReport:
    if ctx.task.report is None:
        report = TaskReport(task_id=ctx.task.id, updated_by=ctx.user.id)
        db.add(report)
        await db.flush()
        ctx.task.report = report
    return ctx.task.report


async def add_task_file(db: AsyncSession, ctx: TaskContext, upload: UploadFile) -> TaskAttachment:
    permissions.authorize(Action.ADD_ATTACHMENT_TASK, ctx.role, is_admin=ctx.user.is_admin)
    if not upload.filename or not upload.filename.strip():
        raise errors.unsupported_filename()
    if await _count_files(db, TaskAttachment, ctx.task.id) >= settings.max_files_per_task:
        raise errors.attachments_limit()
    data = await _read_limited(upload)
    await _ensure_total_within_limit(db, ctx.task.id, len(data))
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
    permissions.authorize(Action.ADD_ATTACHMENT_TASK, ctx.role, is_admin=ctx.user.is_admin)
    _validate_link(url)
    att = TaskAttachment(task_id=ctx.task.id, kind=AttachKind.URL, url=url, uploaded_by=ctx.user.id)
    db.add(att)
    await db.commit()
    return att


async def add_report_file(db: AsyncSession, ctx: TaskContext, upload: UploadFile) -> ReportAttachment:
    permissions.authorize(Action.ADD_REPORT, ctx.role, is_admin=ctx.user.is_admin)
    if not upload.filename or not upload.filename.strip():
        raise errors.unsupported_filename()
    await _ensure_report(db, ctx)
    if await _count_files(db, ReportAttachment, ctx.task.id) >= settings.max_files_per_report:
        raise errors.attachments_limit()
    data = await _read_limited(upload)
    await _ensure_total_within_limit(db, ctx.task.id, len(data))
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
    permissions.authorize(Action.ADD_REPORT, ctx.role, is_admin=ctx.user.is_admin)
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
        permissions.authorize(
            Action.ADD_ATTACHMENT_TASK, ctx.role, is_admin=ctx.user.is_admin
        )  # task-вложение → постановщик
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
    permissions.authorize(
        Action.ADD_REPORT, ctx.role, is_admin=ctx.user.is_admin
    )  # report-вложение → исполнитель
    if report_att.file_path:
        storage.delete(report_att.file_path)
    await db.delete(report_att)
    await db.commit()


def _validate_link(url: str) -> None:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise errors.validation_error([{"field": "url", "message": "Ссылка должна быть http(s)."}])


# --- Создание задачи с вложениями (§6) ---
#
# Эти помощники переиспользуют те же лимиты/чтение, что и пост-загрузка к
# существующей задаче, но НЕ трогают БД и сторадж до тех пор, пока вызывающая
# сторона (task_service) не подтвердит транзакцию. Так создание задачи с
# вложениями остаётся атомарным, а компенсация удаляет уже записанные файлы.


async def prepare_task_files(uploads: Sequence[UploadFile]) -> list[PreparedFile]:
    """Проверяет и читает в память файлы для НОВОЙ задачи без записи в сторадж/БД.

    Применяет те же правила, что и `add_task_file`: имя файла, лимит числа файлов
    на задачу, размер одного файла (потоково в `_read_limited`) и суммарный размер
    задачи `MAX_TASK_TOTAL_MB`. При нарушении бросает доменную ошибку (415/409/413)
    ДО какой-либо записи — задача и файлы не создаются.
    """
    prepared: list[PreparedFile] = []
    if not uploads:
        return prepared
    if len(uploads) > settings.max_files_per_task:
        raise errors.attachments_limit()
    max_total = settings.max_task_total_mb * 1024 * 1024
    total = 0
    for upload in uploads:
        if not upload.filename or not upload.filename.strip():
            raise errors.unsupported_filename()
        data = await _read_limited(upload)
        total += len(data)
        if total > max_total:
            raise errors.task_total_size_limit()
        prepared.append(
            PreparedFile(filename=upload.filename, content_type=upload.content_type, data=data)
        )
    return prepared


def persist_prepared_files(
    db: AsyncSession,
    task_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    prepared: Sequence[PreparedFile],
) -> list[str]:
    """Пишет проверенные файлы в сторадж и добавляет строки `TaskAttachment`.

    Возвращает список сохранённых ключей стораджа для компенсации (удаления при
    откате транзакции вызывающей стороной). Если сбой происходит ПО ХОДУ записи
    (например, диск переполнен на N-м файле), уже записанные файлы удаляются
    здесь же — чтобы не осталось «осиротевших» файлов (Req 1.5). Коммит — за
    вызывающей стороной.
    """
    storage = get_storage()
    written: list[str] = []
    try:
        for pf in prepared:
            stored = storage.save(task_id, pf.data)
            written.append(stored.stored_key)
            db.add(
                TaskAttachment(
                    task_id=task_id,
                    kind=AttachKind.FILE,
                    file_path=stored.stored_key,
                    original_name=pf.filename,
                    mime_type=pf.content_type,
                    size_bytes=stored.size,
                    uploaded_by=uploaded_by,
                )
            )
    except Exception:
        storage.delete_many(written)
        raise
    return written
