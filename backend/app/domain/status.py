"""Статус-машина задачи на основе проверки (§5, design.md «Статусы»).

Стартовое значение — `in_progress`. Исполнитель отправляет работу на проверку
(`under_review`); приёмщик (наблюдатель/администратор) принимает (`done`) или
возвращает на доработку (`rework`); из доработки исполнитель снова отправляет
на проверку. Постановщик/администратор может отменить открытую задачу
(`cancelled`) или переоткрыть закрытую (`in_progress`).

```
in_progress ─submit→ under_review ─accept→ done
                          │
                          └─reject→ rework ─submit→ under_review
* (кроме done) ─cancel→ cancelled
done | cancelled ─reopen→ in_progress
```
"""

from __future__ import annotations

from app.core.errors import status_conflict
from app.domain.enums import TaskStatus

# Допустимые переходы: из какого статуса в какие можно перейти (self-переход —
# идемпотентный no-op и всегда разрешён).
_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.IN_PROGRESS: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.UNDER_REVIEW,
        TaskStatus.CANCELLED,
    },
    TaskStatus.UNDER_REVIEW: {
        TaskStatus.UNDER_REVIEW,
        TaskStatus.DONE,
        TaskStatus.REWORK,
        TaskStatus.IN_PROGRESS,  # переоткрытие/возврат в работу
        TaskStatus.CANCELLED,
    },
    TaskStatus.REWORK: {
        TaskStatus.REWORK,
        TaskStatus.UNDER_REVIEW,
        TaskStatus.CANCELLED,
    },
    TaskStatus.DONE: {TaskStatus.DONE, TaskStatus.IN_PROGRESS},
    TaskStatus.CANCELLED: {TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS},
}

# Закрытые статусы: задача не подлежит напоминаниям/расчёту просрочки.
_CLOSED: set[TaskStatus] = {TaskStatus.DONE, TaskStatus.CANCELLED}


def validate_transition(current: TaskStatus, new: TaskStatus) -> None:
    """Бросает 409 STATUS_CONFLICT при недопустимом переходе."""
    if new not in _TRANSITIONS[current]:
        raise status_conflict()


def is_open(status: TaskStatus) -> bool:
    """Открыта (под напоминаниями/просрочкой) — всё, кроме done/cancelled."""
    return status not in _CLOSED
