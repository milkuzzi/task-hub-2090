"""Интеграция: график 4 уведомлений — получатели, тайминг, краевые,
идемпотентность, best-effort MAX (§13.7.3 Д)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core import clock
from app.domain.enums import DueMode, TaskStatus
from app.models import NotificationLog
from app.notifications.channel import ChannelKind
from app.notifications.registry import set_channels
from app.repositories import outbox_repo
from app.services import notification_service
from tests.factories import make_task, make_user
from tests.fakes import FakeChannel

TZ = ZoneInfo("Europe/Moscow")


def _bodies_to(fake, email):
    return [s["body"] for s in fake.sent if s["to"] == email]


async def test_event1_to_assignee_and_observers_only(db, fake_channels):
    email, _ = fake_channels
    author = await make_user(db, "author@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    obs1 = await make_user(db, "o1@s.ru")
    obs2 = await make_user(db, "o2@s.ru")
    due = clock.now() + timedelta(days=10)  # далеко → только событие 1
    await make_task(db, author, assignee, observers=[obs1, obs2], due_at=due)

    await notification_service.daily_run(db, clock.today())
    recipients = set(email.recipients())
    assert {"asg@s.ru", "o1@s.ru", "o2@s.ru"} <= recipients
    assert "author@s.ru" not in recipients  # постановщик не уведомляется
    # наблюдатель получает только событие 1
    assert len(_bodies_to(email, "o1@s.ru")) == 1


async def test_idempotent_rerun_no_duplicates(db, fake_channels):
    email, _ = fake_channels
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    task = await make_task(db, author, assignee, due_at=clock.now() + timedelta(days=10))

    run_date = clock.today()
    await notification_service.daily_run(db, run_date)
    count1 = await outbox_repo.count_for_task(db, task.id)
    sent1 = len(email.sent)

    await notification_service.daily_run(db, run_date)  # повтор того же дня
    assert await outbox_repo.count_for_task(db, task.id) == count1
    assert len(email.sent) == sent1  # ни одной новой отправки


async def test_created_on_due_date_skips_tomorrow_fires_today(db, fake_channels):
    email, _ = fake_channels
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    today = clock.today()
    due_dt = datetime.combine(today, time(18, 0), tzinfo=TZ)
    await make_task(db, author, assignee, due_at=due_dt, due_mode=DueMode.DATETIME)

    await notification_service.daily_run(db, today)
    bodies = _bodies_to(email, "asg@s.ru")
    assert any("истекает сегодня" in b for b in bodies)  # событие 3
    assert not any("Завтра" in b for b in bodies)  # событие 2 пропущено


async def test_overdue_daily_only_while_open(db, fake_channels):
    email, _ = fake_channels
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    past_due = datetime.combine(clock.today() - timedelta(days=2), time(12, 0), tzinfo=TZ)
    task = await make_task(db, author, assignee, due_at=past_due, due_mode=DueMode.DATETIME)

    await notification_service.daily_run(db, clock.today())
    assert any("просрочена" in b.lower() for b in _bodies_to(email, "asg@s.ru"))  # событие 4

    # после закрытия — ежедневные напоминания прекращаются
    task.status = TaskStatus.DONE
    await db.commit()
    email.sent.clear()
    await notification_service.daily_run(db, clock.today() + timedelta(days=1))
    assert not any("просрочена" in b.lower() for b in _bodies_to(email, "asg@s.ru"))


async def test_max_down_does_not_block_email(db):
    email = FakeChannel(ChannelKind.EMAIL)
    mx = FakeChannel(ChannelKind.MAX, fail=True)
    set_channels({ChannelKind.EMAIL: email, ChannelKind.MAX: mx})
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "asg@s.ru", max_contact="chat-123")
    task = await make_task(db, author, assignee, due_at=clock.now() + timedelta(days=10))

    await notification_service.daily_run(db, clock.today())
    rows = (
        await db.execute(
            select(NotificationLog).where(
                NotificationLog.task_id == task.id, NotificationLog.recipient_id == assignee.id
            )
        )
    ).scalars().all()
    assert any(r.email_status == "delivered" for r in rows)  # почта дошла
    assert any(r.max_status == "failed" for r in rows)  # MAX упал, но не заблокировал


async def test_due_change_refires_under_new_version(db, fake_channels):
    from app.api.deps import TaskContext
    from app.domain.enums import TaskRole
    from app.schemas.tasks import TaskUpdateIn
    from app.services import task_service
    from tests.factories import current_of

    email, _ = fake_channels
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    today = clock.today()
    due_dt = datetime.combine(today, time(18, 0), tzinfo=TZ)
    task = await make_task(db, author, assignee, due_at=due_dt, due_mode=DueMode.DATETIME)

    await notification_service.daily_run(db, today)  # due_today (v1)
    old_version = task.due_version

    # отодвигаем срок на завтра → due_version++
    ctx = TaskContext(task=task, user=current_of(author), role=TaskRole.AUTHOR)
    tomorrow_dt = datetime.combine(today + timedelta(days=1), time(18, 0), tzinfo=TZ)
    await task_service.update_task(db, ctx, TaskUpdateIn(due_at=tomorrow_dt))
    assert task.due_version == old_version + 1

    email.sent.clear()
    await notification_service.daily_run(db, today)  # теперь due_tomorrow (v2)
    assert any("Завтра" in b for b in _bodies_to(email, "asg@s.ru"))
