"""Чистая логика графика из 4 событий (§9, §13.4.3).

Определяет, какое плановое напоминание (2–4) полагается открытой задаче в
конкретный суточный прогон `run_date`. Событие 1 (постановка) обрабатывается
отдельно — оно одноразовое и не зависит от даты прогона (дедуп по журналу).
"""

from __future__ import annotations

from datetime import date, timedelta

from app.domain.enums import NotifyEvent


def due_event_for(run_date: date, due_date: date) -> NotifyEvent | None:
    """Плановое напоминание для ОТКРЫТОЙ задачи в прогоне `run_date`.

    - `run_date == due_date - 1` → за сутки (DUE_TOMORROW);
    - `run_date == due_date`     → в день срока (DUE_TODAY);
    - `run_date > due_date`      → ежедневно после срока (OVERDUE_DAILY);
    - иначе                      → None (ещё рано).
    """
    if run_date == due_date - timedelta(days=1):
        return NotifyEvent.DUE_TOMORROW
    if run_date == due_date:
        return NotifyEvent.DUE_TODAY
    if run_date > due_date:
        return NotifyEvent.OVERDUE_DAILY
    return None
