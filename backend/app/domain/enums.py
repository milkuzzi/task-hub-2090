"""Перечисляемые типы — замороженный контракт (§13.0, §13.2.3, §13.3.6).

Строковые значения load-bearing: они одновременно метки PostgreSQL ENUM,
коды в API/DTO и значения во фронтенде. Менять нельзя без миграции.
"""

from __future__ import annotations

from enum import StrEnum


class TaskRole(StrEnum):
    """Роль пользователя ПО КОНКРЕТНОЙ задаче (вычисляется на лету, §4)."""

    AUTHOR = "author"  # постановщик
    ASSIGNEE = "assignee"  # исполнитель (ровно один)
    OBSERVER = "observer"  # наблюдатель (до 5)
    NONE = "none"  # нет доступа


class TaskStatus(StrEnum):
    """Статус задачи — управляется постановщиком (§5)."""

    IN_PROGRESS = "in_progress"  # В работе (стартовое)
    DONE = "done"  # Выполнена
    CANCELLED = "cancelled"  # Отменена


class DueMode(StrEnum):
    """Режим срока (§5)."""

    DATETIME = "datetime"  # дата + время
    DATE = "date"  # только дата


class AttachKind(StrEnum):
    """Вид вложения (§5)."""

    FILE = "file"
    URL = "url"


class NotifyEvent(StrEnum):
    """4 события графика напоминаний (§9)."""

    ASSIGNED = "assigned"  # день постановки
    DUE_TOMORROW = "due_tomorrow"  # за сутки до срока
    DUE_TODAY = "due_today"  # в день срока
    OVERDUE_DAILY = "overdue_daily"  # ежедневно после срока


class NotifyChannel(StrEnum):
    """Каналы доставки (§9). push/sms — задел, не реализуются."""

    EMAIL = "email"
    MAX = "max"
    PUSH = "push"  # задел
    SMS = "sms"  # задел


class Action(StrEnum):
    """Действия над задачей для матрицы прав (§6, §13.3.6)."""

    VIEW = "view"
    EDIT_FIELDS = "edit_fields"
    DELETE_TASK = "delete_task"
    CHANGE_STATUS = "change_status"
    ADD_REPORT = "add_report"
    MARK_READY = "mark_ready"
    ADD_ATTACHMENT_TASK = "add_attachment_task"
    EXPORT = "export"


# Человекочитаемые русские метки статуса для печати/писем (канон — коды выше).
STATUS_LABELS_RU: dict[TaskStatus, str] = {
    TaskStatus.IN_PROGRESS: "В работе",
    TaskStatus.DONE: "Выполнена",
    TaskStatus.CANCELLED: "Отменена",
}
