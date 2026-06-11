"""Сборка DTO из ORM-моделей (§13.5, §13.6.4).

Эффективная просрочка для отображения: материализованный флаг ИЛИ «по факту»
для открытой задачи (на случай, если sweep ещё не отработал) (§13.6.2).
"""

from __future__ import annotations

from app.api.routes import attachment_download_path
from app.core.clock import now
from app.domain.enums import AttachKind, DueMode, TaskStatus
from app.domain.overdue import is_overdue
from app.models import ReportAttachment, Task, TaskAttachment, TaskObserver, User
from app.schemas.common import AttachmentOut, ReportOut, TaskDetailOut, TaskListItemOut, UserRefOut


def user_ref(user: User) -> UserRefOut:
    return UserRefOut(
        id=user.id, email=user.email, display_name=user.display_name, is_deleted=user.is_deleted
    )


def observer_ref(obs: TaskObserver) -> UserRefOut:
    return UserRefOut(
        id=obs.user_id,
        email=obs.user.email if obs.user else "",
        display_name=obs.display_name,
        is_deleted=obs.user.is_deleted if obs.user else True,
    )


def attachment_out(att: TaskAttachment | ReportAttachment, *, task_id) -> AttachmentOut:
    if att.kind == AttachKind.FILE:
        return AttachmentOut(
            id=att.id,
            kind=AttachKind.FILE,
            filename=att.original_name,
            size=att.size_bytes,
            content_type=att.mime_type,
            download_url=attachment_download_path(task_id, att.id),
        )
    return AttachmentOut(
        id=att.id,
        kind=AttachKind.URL,
        filename=att.url,
        url=att.url,
        download_url=att.url,
    )


def _effective_overdue(task: Task) -> bool:
    if task.is_overdue:
        return True
    if task.status == TaskStatus.IN_PROGRESS:
        return is_overdue(now(), task.due_at, task.due_mode)
    return False


def task_list_item(task: Task) -> TaskListItemOut:
    return TaskListItemOut(
        id=task.id,
        seq_no=task.task_no,
        code=f"{task.code6:06d}",
        title=task.title,
        deadline=task.due_at,
        deadline_has_time=(task.due_mode == DueMode.DATETIME),
        status=task.status,
        is_overdue=_effective_overdue(task),
        needs_reassignment=task.needs_reassignment,
        assignee=user_ref(task.assignee),
        author=user_ref(task.author),
        observers=[observer_ref(o) for o in task.observers],
        assignee_marked_ready=bool(task.report and task.report.ready_flag),
    )


def task_detail(task: Task) -> TaskDetailOut:
    base = task_list_item(task)
    report_out: ReportOut | None = None
    if task.report is not None:
        report_out = ReportOut(
            text=task.report.text,
            attachments=[attachment_out(a, task_id=task.id) for a in task.report.attachments],
            ready=task.report.ready_flag,
            ready_at=task.report.ready_at,
            updated_at=task.report.updated_at,
        )
    return TaskDetailOut(
        **base.model_dump(by_alias=False),
        description=task.description,
        attachments=[attachment_out(a, task_id=task.id) for a in task.attachments],
        report=report_out,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
