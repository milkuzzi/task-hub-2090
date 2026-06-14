"""Декларативная политика прав — машинная копия таблицы прав (§6, design.md).

Единственный источник истины «действие → допустимые роли». Любая мутация
проходит через `authorize(...)` в сервисном слое — обойти через альтернативный
эндпойнт нельзя. Администратор не имеет роли по задаче, но получает доступ к
части действий через override `is_admin` (а не через таблицу прав).
"""

from __future__ import annotations

from app.core.errors import forbidden_role
from app.domain.enums import Action, TaskRole

ALLOWED: dict[Action, set[TaskRole]] = {
    Action.VIEW: {TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER},
    Action.EDIT_FIELDS: {TaskRole.AUTHOR},
    Action.DELETE_TASK: {TaskRole.AUTHOR},
    Action.CHANGE_STATUS: {TaskRole.AUTHOR},  # отмена/переоткрытие — постановщик
    Action.ADD_ATTACHMENT_TASK: {TaskRole.AUTHOR},  # вложение к задаче — постановщик
    Action.ADD_REPORT: {TaskRole.ASSIGNEE},  # отчёт и вложение к отчёту — исполнитель
    Action.MARK_READY: {TaskRole.ASSIGNEE},
    Action.SUBMIT_REVIEW: {TaskRole.ASSIGNEE},  # «готово к проверке» — только исполнитель
    Action.DECIDE_REVIEW: {TaskRole.OBSERVER},  # приёмка — наблюдатель (+admin override)
    Action.POST_MESSAGE: {TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER},
    Action.EXPORT: {TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER},
}

# Действия, доступные администратору поверх роли по задаче. SUBMIT_REVIEW и
# ADD_REPORT/MARK_READY НЕ входят — отчитываться/отправлять на проверку может
# только сам исполнитель (Req 5.4, design.md).
ADMIN_OVERRIDE: set[Action] = {
    Action.VIEW,
    Action.EXPORT,
    Action.EDIT_FIELDS,
    Action.DELETE_TASK,
    Action.CHANGE_STATUS,
    Action.DECIDE_REVIEW,
    Action.POST_MESSAGE,
}


def can(action: Action, role: TaskRole) -> bool:
    return role in ALLOWED[action]


def authorize(action: Action, role: TaskRole, *, is_admin: bool = False) -> None:
    """Бросает 403 FORBIDDEN_ROLE, если роль (или админ-override) не даёт права."""
    if is_admin and action in ADMIN_OVERRIDE:
        return
    if not can(action, role):
        raise forbidden_role()
