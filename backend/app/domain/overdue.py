"""Логика просрочки (§5, §13.4.2).

«Просрочена» — независимый факт, а не статус. Момент перехода:
  - режим «дата+время»: ровно `due_at`;
  - режим «только дата»: начало следующих суток после даты срока
    (в конце дня-срока ещё НЕ просрочена).

Граница включительна: `now >= due_moment` → просрочена.
"""

from __future__ import annotations

from datetime import date, datetime

from app.core.clock import next_day_start, to_org_tz
from app.domain.enums import DueMode


def due_moment(due_at: datetime, due_mode: DueMode) -> datetime:
    """Момент, с которого задача считается просроченной (tz-aware, TZ организации)."""
    due_at = to_org_tz(due_at)
    if due_mode == DueMode.DATETIME:
        return due_at
    # «только дата»: просрочка с началом следующих суток после даты срока
    return next_day_start(due_at.date())


def is_overdue(now: datetime, due_at: datetime, due_mode: DueMode) -> bool:
    """«По факту»: достоверно при чтении даже без прогона воркера."""
    return to_org_tz(now) >= due_moment(due_at, due_mode)


def due_date_local(due_at: datetime) -> date:
    """Календарная дата срока в таймзоне организации (для графика уведомлений §9)."""
    return to_org_tz(due_at).date()
