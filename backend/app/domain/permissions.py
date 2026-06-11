"""Декларативная политика прав — машинная копия таблицы §6 (§13.3.6).

Единственный источник истины «действие → допустимые роли». Любая мутация
проходит через `authorize(...)` в сервисном слое — обойти через альтернативный
эндпойнт нельзя.
"""

from __future__ import annotations

from app.core.errors import forbidden_role
from app.domain.enums import Action, TaskRole

ALLOWED: dict[Action, set[TaskRole]] = {
    Action.VIEW: {TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER},
    Action.EDIT_FIELDS: {TaskRole.AUTHOR},
    Action.DELETE_TASK: {TaskRole.AUTHOR},
    Action.CHANGE_STATUS: {TaskRole.AUTHOR},
    Action.ADD_ATTACHMENT_TASK: {TaskRole.AUTHOR},  # вложение к задаче — постановщик
    Action.ADD_REPORT: {TaskRole.ASSIGNEE},  # отчёт и вложение к отчёту — исполнитель
    Action.MARK_READY: {TaskRole.ASSIGNEE},
    Action.EXPORT: {TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER},
}


def can(action: Action, role: TaskRole) -> bool:
    return role in ALLOWED[action]


def authorize(action: Action, role: TaskRole) -> None:
    """Бросает 403 FORBIDDEN_ROLE, если роль не имеет права на действие."""
    if not can(action, role):
        raise forbidden_role()
