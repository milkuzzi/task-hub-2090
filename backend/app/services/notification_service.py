"""Подсистема уведомлений: материализация флага просрочки и суточный прогон
графика из 4 событий с идемпотентностью (§9, §13.4)."""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.core.clock import now, start_of_day, to_org_tz, today
from app.core.config import settings
from app.db.session import SessionFactory
from app.domain.enums import DueMode, NotifyEvent, TaskStatus
from app.domain.notifications import templates
from app.domain.notifications.schedule import due_event_for
from app.domain.overdue import due_date_local, due_moment, is_overdue
from app.domain.status import is_open
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

log = logging.getLogger("notifications")

# --- Процесс A: материализация флага «Просрочена» (§13.4.2) ---


async def overdue_sweep(db: AsyncSession) -> int:
    """Лёгкий частый проход: проставляет is_overdue/overdue_since по факту.

    Отношения задачи (наблюдатели/вложения/отчёт) намеренно не подгружаем
    (`noload`) — проходу нужны только due_at/due_mode/status, а лишние выборки
    каждые несколько минут зря нагружают воркер на скромном VPS.
    """
    res = await db.execute(
        select(Task)
        .options(noload("*"))
        .where(
            Task.status.notin_((TaskStatus.DONE, TaskStatus.CANCELLED)),
            Task.is_overdue.is_(False),
        )
    )
    moment_now = now()
    changed = 0
    for task in res.scalars().all():
        if is_overdue(moment_now, task.due_at, task.due_mode):
            task.is_overdue = True
            # Фиксируем фактический момент наступления просрочки (неизменяем),
            # а не время прохода sweep — иначе значение «опаздывает» после простоя.
            task.overdue_since = due_moment(task.due_at, task.due_mode)
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


async def _emit_assigned(db: AsyncSession, task: Task) -> None:
    """Событие №1 (постановка): исполнители + наблюдатели, одноразово (идемпотентно)."""
    for ta in task.assignees:
        if ta.user is not None:
            await _emit(
                db,
                task,
                NotifyEvent.ASSIGNED,
                ta.user,
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


async def notify_assignment(task_id: uuid.UUID) -> None:
    """Разослать уведомление о постановке сразу при создании задачи (§9, событие 1).

    Запускается фоном после ответа API (FastAPI BackgroundTasks): открывает
    собственную сессию, чтобы не блокировать HTTP-ответ ожиданием SMTP.
    Идемпотентность общая с суточным прогоном — повторов не будет.
    """
    async with SessionFactory() as db:
        task = await tasks_repo.get_full(db, task_id)
        if task is None:
            return
        try:
            await _emit_assigned(db, task)
        except Exception:  # noqa: BLE001 — фоновая рассылка не должна падать наружу
            log.exception("notify_assignment: ошибка рассылки для задачи %s", task_id)


async def daily_run(db: AsyncSession, run_date: date | None = None) -> None:
    """Раз в сутки: события 1–4 (§13.4.5)."""
    run_date = run_date or today()
    # Ограничиваем выборку: открытые задачи + недавно созданные (страховка по
    # событию №1). Иначе прогон линейно растёт по всей истории задач.
    recent_since = start_of_day(run_date - timedelta(days=2))
    tasks = await tasks_repo.iter_active_tasks_for_notifications(db, recent_since=recent_since)

    for task in tasks:
        # СОБЫТИЕ 1 — постановка (исполнитель + наблюдатели), одноразово
        await _emit_assigned(db, task)

        # СОБЫТИЯ 2–4 — только для открытых задач, всем исполнителям
        if not is_open(task.status):
            continue
        dl = due_date_local(task.due_at)
        event = due_event_for(run_date, dl)
        if event is not None:
            for ta in task.assignees:
                if ta.user is not None:
                    await _emit(
                        db,
                        task,
                        event,
                        ta.user,
                        _message_for(task, event, is_observer=False),
                        due_version=task.due_version,
                        run_date=run_date,
                    )
