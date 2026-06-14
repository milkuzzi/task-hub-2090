"""Роутер задач: CRUD, статус, отчёт, готовность, вложения, поиск, выгрузка (§13.5.4).

Статические пути (`/search`, `/export`) объявлены ДО `/{task_id}`, иначе FastAPI
сматчит их как идентификатор задачи.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, TaskContext, get_current_user, get_task_context
from app.api.presenters import attachment_out, task_detail, task_list_item
from app.core import errors
from app.db.session import get_db
from app.domain.enums import AttachKind, TaskStatus
from app.schemas.chat import MessageIn, MessageListOut, MessageOut
from app.schemas.common import (
    AttachmentOut,
    OkResponse,
    TaskDetailOut,
    TaskListResponse,
)
from app.schemas.reports import MarkReadyIn, MarkReadyOut, ReportIn
from app.schemas.tasks import ReviewDecisionIn, StatusIn, TaskCreateIn, TaskUpdateIn
from app.services import (
    attachment_service,
    chat_service,
    export_service,
    notification_service,
    report_service,
    task_service,
)
from app.storage.base import get_storage

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _parse_status(value: str | None) -> TaskStatus | None:
    if value is None:
        return None
    try:
        return TaskStatus(value)
    except ValueError:
        raise errors.bad_request("Неизвестный статус.") from None


def _parse_task_payload(payload: str) -> TaskCreateIn:
    """Парсит JSON-строку `payload` мультипарта в TaskCreateIn.

    Сначала валидируем форму через ту же схему, что и раньше (чёткие ошибки по
    полям в том же формате 422 `details`, что и при обычном JSON-теле).
    """
    try:
        return TaskCreateIn.model_validate_json(payload)
    except ValidationError as exc:
        details = [
            {
                "field": ".".join(str(p) for p in e.get("loc", ()) if p != "body"),
                "message": e.get("msg", ""),
            }
            for e in exc.errors()
        ]
        raise errors.validation_error(details) from exc


# --- Список / создание ---


@router.post("", response_model=TaskDetailOut, status_code=201)
async def create_task(
    background: BackgroundTasks,
    payload: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создание задачи с вложениями (§6).

    Контракт `multipart/form-data`:
      - `payload` — JSON-строка с телом задачи (та же форма, что TaskCreateIn:
        title, description, dueAt, dueMode, assigneeIds, observerIds, links);
      - `files` — ноль или более файлов-вложений.
    Задача и все вложения создаются атомарно (см. task_service.create_task).
    """
    body = _parse_task_payload(payload)
    task = await task_service.create_task(db, user, body, files=files)
    # Уведомление о постановке (§9, событие 1) — сразу, но фоном: не блокируем
    # ответ ожиданием SMTP. Идемпотентность общая с суточным прогоном.
    background.add_task(notification_service.notify_assignment, task.id)
    return task_detail(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    role: str = Query(...),
    status: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks, total = await task_service.list_tasks(
        db,
        user,
        role=role,
        status_filter=_parse_status(status),
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return TaskListResponse(
        items=[task_list_item(t) for t in tasks], total=total, page=page, page_size=page_size
    )


# --- Поиск и выгрузка (до /{task_id}) ---


@router.get("/search", response_model=TaskDetailOut)
async def search_by_code(
    code: str = Query(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not (code.isdigit() and len(code) == 6):
        raise errors.validation_error([{"field": "code", "message": "Код должен быть 6-значным."}])
    task = await task_service.search_by_code(db, user, int(code))
    return task_detail(task)


@router.get("/export")
async def export_tasks(
    role: str = Query(...),
    format: str = Query(default="print"),
    status: str | None = Query(default=None),
    sort: str | None = Query(default=None),
    order: str = Query(default="asc"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    html = await export_service.render_print(
        db, user, role=role, status_filter=_parse_status(status), sort=sort, order=order
    )
    return HTMLResponse(content=html)


# --- Карточка задачи ---


@router.get("/{task_id}", response_model=TaskDetailOut)
async def get_task(ctx: TaskContext = Depends(get_task_context)):
    return task_detail(ctx.task)


@router.put("/{task_id}", response_model=TaskDetailOut)
async def update_task(
    body: TaskUpdateIn,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.update_task(db, ctx, body)
    return task_detail(task)


@router.delete("/{task_id}", response_model=OkResponse)
async def delete_task(
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    await task_service.delete_task(db, ctx)
    return OkResponse()


@router.patch("/{task_id}/status", response_model=TaskDetailOut)
async def change_status(
    body: StatusIn,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.change_status(db, ctx, body.status)
    return task_detail(task)


@router.post("/{task_id}/submit-review", response_model=TaskDetailOut)
async def submit_review(
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    """Исполнитель: «Готово к проверке» → статус under_review."""
    task = await task_service.submit_review(db, ctx)
    return task_detail(task)


@router.post("/{task_id}/review", response_model=TaskDetailOut)
async def review_decision(
    body: ReviewDecisionIn,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    """Приёмщик (наблюдатель/админ): принять (done) или вернуть на доработку (rework)."""
    task = await task_service.review_decision(db, ctx, body.decision)
    return task_detail(task)


# --- Чат задачи (§4) ---


@router.get("/{task_id}/messages", response_model=MessageListOut)
async def list_messages(
    after: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    """История сообщений чата. `after` — курсор по createdAt для дозагрузки."""
    return await chat_service.list_messages(db, ctx, after=after, limit=limit)


@router.post("/{task_id}/messages", response_model=MessageOut, status_code=201)
async def post_message(
    body: MessageIn,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    """Отправка сообщения в чат (право POST_MESSAGE). Доставка участникам по WS."""
    return await chat_service.post_message(db, ctx, body.body)


# --- Отчёт и готовность ---


@router.post("/{task_id}/report", response_model=TaskDetailOut, status_code=201)
async def add_report(
    body: ReportIn,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    task = await report_service.add_report(db, ctx, text=body.text)
    return task_detail(task)


@router.post("/{task_id}/mark-ready", response_model=MarkReadyOut)
async def mark_ready(
    body: MarkReadyIn,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    report = await report_service.mark_ready(db, ctx, text=body.text)
    return MarkReadyOut(ready=report.ready_flag, ready_at=report.ready_at)


# --- Вложения ---


@router.post("/{task_id}/attachments", response_model=AttachmentOut, status_code=201)
async def add_attachment(
    scope: str = Query(default="task"),
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    if scope not in ("task", "report"):
        raise errors.bad_request("scope должен быть task или report.")
    if file is not None:
        if scope == "task":
            att = await attachment_service.add_task_file(db, ctx, file)
        else:
            att = await attachment_service.add_report_file(db, ctx, file)
    elif url:
        if scope == "task":
            att = await attachment_service.add_task_link(db, ctx, url)
        else:
            att = await attachment_service.add_report_link(db, ctx, url)
    else:
        raise errors.validation_error([{"field": "file", "message": "Нужен файл или ссылка."}])
    return attachment_out(att, task_id=ctx.task.id)


@router.get("/{task_id}/attachments/{att_id}/download")
async def download_attachment(
    att_id: uuid.UUID,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    target = await attachment_service.get_download(db, ctx, att_id)
    if target.kind == AttachKind.URL:
        return JSONResponse({"url": target.url})
    path = get_storage().path_of(target.path or "")
    if not path.exists():
        raise errors.attachment_not_found()
    return FileResponse(
        path,
        media_type=target.mime_type or "application/octet-stream",
        filename=target.filename or "file",
        content_disposition_type="attachment",
    )


@router.delete("/{task_id}/attachments/{att_id}", response_model=OkResponse)
async def delete_attachment(
    att_id: uuid.UUID,
    ctx: TaskContext = Depends(get_task_context),
    db: AsyncSession = Depends(get_db),
):
    await attachment_service.delete_attachment(db, ctx, att_id)
    return OkResponse()
