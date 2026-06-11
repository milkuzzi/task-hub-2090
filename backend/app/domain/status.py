"""Статус-машина задачи (§5, §13.3.7).

Стартовое значение — `in_progress`. Постановщик может закрыть задачу
(`done`/`cancelled`) или вернуть в работу. Из закрытого состояния разрешён
только возврат `in_progress` (переоткрытие) — прямой переход `done`↔`cancelled`
без возврата в работу запрещён.
"""

from __future__ import annotations

from app.core.errors import status_conflict
from app.domain.enums import TaskStatus

# Допустимые переходы: из какого статуса в какие можно перейти.
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.IN_PROGRESS: {TaskStatus.DONE, TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS},
    TaskStatus.DONE: {TaskStatus.IN_PROGRESS, TaskStatus.DONE},
    TaskStatus.CANCELLED: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
}


def validate_transition(current: TaskStatus, new: TaskStatus) -> None:
    """Бросает 409 STATUS_CONFLICT при недопустимом переходе."""
    if new not in _TRANSITIONS[current]:
        raise status_conflict()


def is_open(status: TaskStatus) -> bool:
    return status == TaskStatus.IN_PROGRESS
