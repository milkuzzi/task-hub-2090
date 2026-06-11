"""Единый источник «сейчас» в таймзоне организации.

ОБЯЗАТЕЛЬНОЕ требование тестопригодности (§13.0, §13.7.2): весь backend берёт
текущее время ТОЛЬКО через `now()` отсюда. Прямые вызовы `datetime.now()` /
`datetime.utcnow()` вне этого модуля запрещены — иначе `freezegun`/подмена не
накроют фоновые модули (планировщик, расчёт просрочки).

В тестах время подменяется через `set_now_override()` (надёжнее, чем module-walk
freezegun) либо через freezegun поверх делегирующего `datetime.now(tz)`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings

ORG_TZ = ZoneInfo(settings.tz)

# Подменяемый источник времени для тестов. None → реальное время.
_now_override: Callable[[], datetime] | None = None


def now() -> datetime:
    """Текущий момент, tz-aware, в таймзоне организации."""
    if _now_override is not None:
        value = _now_override()
        if value.tzinfo is None:
            return value.replace(tzinfo=ORG_TZ)
        return value.astimezone(ORG_TZ)
    return datetime.now(ORG_TZ)


def today() -> date:
    """Календарная дата «сегодня» в таймзоне организации."""
    return now().date()


def start_of_day(d: date) -> datetime:
    """Начало суток (00:00:00) указанной даты в таймзоне организации."""
    return datetime(d.year, d.month, d.day, tzinfo=ORG_TZ)


def end_of_day(d: date) -> datetime:
    """Конец суток (23:59:59) указанной даты в таймзоне организации."""
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=ORG_TZ)


def next_day_start(d: date) -> datetime:
    """Начало следующих суток после даты — момент перехода в «Просрочена»
    для режима «только дата» (§5/§9 ТЗ)."""
    return start_of_day(d + timedelta(days=1))


def set_now_override(fn: Callable[[], datetime] | None) -> None:
    """Подменить источник времени (для тестов)."""
    global _now_override
    _now_override = fn


def to_org_tz(value: datetime) -> datetime:
    """Привести любой aware/naive datetime к таймзоне организации."""
    if value.tzinfo is None:
        return value.replace(tzinfo=ORG_TZ)
    return value.astimezone(ORG_TZ)
