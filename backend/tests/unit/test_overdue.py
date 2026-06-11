"""Юнит: момент просрочки и флаг в обоих режимах, граница и полуночь (§13.7.3 Г)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.enums import DueMode
from app.domain.overdue import due_moment, is_overdue

TZ = ZoneInfo("Europe/Moscow")


def test_datetime_boundary_inclusive():
    due = datetime(2026, 6, 11, 14, 37, tzinfo=TZ)
    assert is_overdue(datetime(2026, 6, 11, 14, 36, tzinfo=TZ), due, DueMode.DATETIME) is False
    # граница == включительно
    assert is_overdue(datetime(2026, 6, 11, 14, 37, tzinfo=TZ), due, DueMode.DATETIME) is True
    assert is_overdue(datetime(2026, 6, 11, 14, 38, tzinfo=TZ), due, DueMode.DATETIME) is True


def test_date_mode_midnight_rollover():
    due = datetime(2026, 6, 11, 23, 59, 59, tzinfo=TZ)  # конец дня-срока (режим date)
    assert due_moment(due, DueMode.DATE) == datetime(2026, 6, 12, 0, 0, 0, tzinfo=TZ)
    # в конце дня-срока ещё НЕ просрочена
    assert is_overdue(datetime(2026, 6, 11, 23, 59, 59, tzinfo=TZ), due, DueMode.DATE) is False
    # с началом следующих суток — просрочена
    assert is_overdue(datetime(2026, 6, 12, 0, 0, 0, tzinfo=TZ), due, DueMode.DATE) is True


def test_datetime_moment_is_due_at():
    due = datetime(2026, 6, 11, 9, 0, tzinfo=TZ)
    assert due_moment(due, DueMode.DATETIME) == due
