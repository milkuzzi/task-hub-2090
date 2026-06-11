"""Подсистема уведомлений: материализация флага просрочки и суточный прогон
графика из 4 событий с идемпотентностью (§9, §13.4)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now, to_org_tz, today
from app.core.config import settings
from app.domain.enums import DueMode, NotifyEvent, TaskStatus
from app.domain.notifications import templates
from app.domain.notifications.schedule import due_event_for
from app.domain.overdue import due_date_local, is_overdue
from app.models import Task, User
from app.notifications.channel import (
    CHANNEL_ORDER,
    Attachment,
    ChannelKind,
    DeliveryStatus,
    Message,
    Recipient,
)
from app.notifications.registry import get_channel
from app.repositories import outbox_repo, registry_repo, tasks_repo
from app.storage.base import get_storage

# --- Процесс A: материализация флага «Просрочена» (§13.4.2) ---


async def overdue_sweep(db: AsyncSession) -> int:
    """Лёгкий частый проход: проставляет is_overdue/overdue_since по факту."""
    res = await db.execute(
        select(Task).where(
            Task.status == TaskStatus.IN_PROGRESS, Task.is_overdue.is_(False)
        )
    )
    moment_now = now()
    changed = 0
    for task in res.unique().scalars().all():
        if is_overdue(moment_now, task.due_at, task.due_mode):
            task.is_overdue = True
            task.overdue_since = moment_now  # факт, не сбрасывается автоматически
            changed += 1
    if changed:
        await db.commit()
    return changed


# --- Процесс B: суточный прогон уведомлений (§13.4.3, §13.4.5) ---


def _due_display(task: Task) -> str:
    dt = to_org_tz(task.due_at)
    if task.due_mode == DueMode.DATETIME:
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%d.%m.%Y")


def _brief(task: Task) -> templates.TaskBrief:
    return templates.TaskBrief(
        seq_no=task.task_no,
        code=f"{task.code6:06d}",
        title=task.title,
        description=task.description or "",
        due_display=_due_display(task),
    )


def _channel_attachments(task: Task) -> list[Attachment]:
    storage = get_storage()
    out: list[Attachment] = []
    for a in task.attachments:
        if a.file_path:
            out.append(
                Attachment(
                    filename=a.original_name or "file",
                    size=a.size_bytes or 0,
                    content_type=a.mime_type or "application/octet-stream",
                    storage_path=str(storage.path_of(a.file_path)),
                    public_url=(
                        f"{settings.base_url.rstrip('/')}/api/v1/tasks/{task.id}"
                        f"/attachments/{a.id}/download"
                    ),
                )
            )
    return out


def _message_for(task: Task, event: NotifyEvent, *, is_observer: bool) -> Message:
    brief = _brief(task)
    if event == NotifyEvent.ASSIGNED:
        subject, body = (
            templates.assigned_observer(brief) if is_observer else templates.assigned_executor(brief)
        )
        attachments = _channel_attachments(task)
    elif event == NotifyEvent.DUE_TOMORROW:
        subject, body = templates.due_tomorrow(brief)
        attachments = []
    elif event == NotifyEvent.DUE_TODAY:
        subject, body = templates.due_today(brief)
        attachments = []
    else:  # OVERDUE_DAILY
        subject, body = templates.overdue_daily(brief)
        attachments = []
    return Message(subject=subject, body_text=body, attachments=attachments, task_code=brief.code)


async def _recipient(db: AsyncSession, user: User) -> Recipient:
    entry = await registry_repo.get_by_email(db, user.email)
    max_ref = entry.max_user_id if entry else None
    return Recipient(user_id=str(user.id), email=user.email, max_ref=max_ref)


async def _emit(
    db: AsyncSession,
    task: Task,
    event: NotifyEvent,
    user: User,
    message: Message,
    *,
    due_version: int | None,
    run_date: date | None,
) -> None:
    if user.is_deleted:
        return  # tombstone-исполнителю/наблюдателю слать некуда
    # 1) Бронь ДО отправки + commit — идемпотентность переживает перезапуск воркера
    reserved = await outbox_repo.reserve(
        db,
        task_id=task.id,
        event_type=event,
        recipient_id=user.id,
        due_version=due_version,
        run_date=run_date,
    )
    await db.commit()
    if not reserved:
        return  # уже отправлено сегодня/в эту версию

    # 2) Доставка по каналам строго в порядке [EMAIL, MAX]
    recipient = await _recipient(db, user)
    results: dict[ChannelKind, DeliveryStatus] = {}
    detail: str | None = None
    for kind in CHANNEL_ORDER:
        ch = get_channel(kind)
        if ch.can_send(recipient):
            res = await ch.send(recipient, message)
            results[kind] = res.status
            if res.detail:
                detail = res.detail
        else:
            results[kind] = DeliveryStatus.SKIPPED

    # 3) Фиксация результатов; почта-failed — кандидат на ретрай
    await outbox_repo.record_results(
        db,
        task_id=task.id,
        event_type=event,
        recipient_id=user.id,
        due_version=due_version,
        run_date=run_date,
        email_status=results[ChannelKind.EMAIL].value,
        max_status=results.get(ChannelKind.MAX, DeliveryStatus.SKIPPED).value,
        detail=detail,
    )
    await db.commit()


async def daily_run(db: AsyncSession, run_date: date | None = None) -> None:
    """Раз в сутки: события 1–4 (§13.4.5)."""
    run_date = run_date or today()
    tasks = await tasks_repo.iter_active_tasks_for_notifications(db)

    for task in tasks:
        assignee = task.assignee

        # СОБЫТИЕ 1 — постановка (исполнитель + наблюдатели), одноразово
        await _emit(
            db,
            task,
            NotifyEvent.ASSIGNED,
            assignee,
            _message_for(task, NotifyEvent.ASSIGNED, is_observer=False),
            due_version=None,
            run_date=None,
        )
        for obs in task.observers:
            if obs.user is not None:
                await _emit(
                    db,
                    task,
                    NotifyEvent.ASSIGNED,
                    obs.user,
                    _message_for(task, NotifyEvent.ASSIGNED, is_observer=True),
                    due_version=None,
                    run_date=None,
                )

        # СОБЫТИЯ 2–4 — только для открытых задач, только исполнителю
        if task.status != TaskStatus.IN_PROGRESS:
            continue
        dl = due_date_local(task.due_at)
        event = due_event_for(run_date, dl)
        if event is not None:
            await _emit(
                db,
                task,
                event,
                assignee,
                _message_for(task, event, is_observer=False),
                due_version=task.due_version,
                run_date=run_date,
            )
