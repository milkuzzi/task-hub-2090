"""Интеграция: флаг «Просрочена» — авто, не статус, факт, переоценка (§13.7.3 Г)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.api.deps import TaskContext
from app.core import clock
from app.domain.enums import DueMode, TaskRole, TaskStatus
from app.schemas.tasks import TaskUpdateIn
from app.services import notification_service, task_service
from tests.factories import current_of, make_task, make_user

TZ = ZoneInfo("Europe/Moscow")


async def test_sweep_sets_flag_without_changing_status(db):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    due = clock.now() + timedelta(hours=1)
    task = await make_task(db, a, b, due_at=due, due_mode=DueMode.DATETIME)

    await notification_service.overdue_sweep(db)
    assert task.is_overdue is False  # ещё не наступил срок

    clock.set_now_override(lambda: due + timedelta(minutes=5))
    await notification_service.overdue_sweep(db)
    assert task.is_overdue is True
    assert task.status == TaskStatus.IN_PROGRESS  # статус не изменился
    assert task.overdue_since is not None


async def test_date_mode_not_overdue_until_next_day(db):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    due_date = clock.today()
    due_dt = datetime.combine(due_date, time(12, 0), tzinfo=TZ)
    task = await make_task(db, a, b, due_at=due_dt, due_mode=DueMode.DATE)

    # конец дня-срока — ещё не просрочена
    clock.set_now_override(lambda: datetime.combine(due_date, time(23, 59, 59), tzinfo=TZ))
    await notification_service.overdue_sweep(db)
    assert task.is_overdue is False

    # начало следующих суток — просрочена
    next_day = datetime.combine(due_date, time(23, 59, 59), tzinfo=TZ) + timedelta(seconds=2)
    clock.set_now_override(lambda: next_day)
    await notification_service.overdue_sweep(db)
    assert task.is_overdue is True


async def test_fact_persists_after_close(db):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    due = clock.now() - timedelta(hours=1)
    task = await make_task(db, a, b, due_at=due, due_mode=DueMode.DATETIME)
    await notification_service.overdue_sweep(db)
    assert task.is_overdue is True

    task.status = TaskStatus.DONE
    await db.commit()
    assert task.is_overdue is True  # факт не обнуляется при закрытии


async def test_due_change_to_future_clears_flag(db):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    due = clock.now() - timedelta(hours=1)
    task = await make_task(db, a, b, due_at=due, due_mode=DueMode.DATETIME)
    await notification_service.overdue_sweep(db)
    assert task.is_overdue is True
    old_version = task.due_version

    ctx = TaskContext(task=task, user=current_of(a), role=TaskRole.AUTHOR)
    new_due = clock.now() + timedelta(days=3)
    updated = await task_service.update_task(db, ctx, TaskUpdateIn(due_at=new_due))
    assert updated.is_overdue is False  # новый срок в будущем → факт снят
    assert updated.due_version == old_version + 1
