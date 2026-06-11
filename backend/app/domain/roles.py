"""Вычисление роли пользователя ПО КОНКРЕТНОЙ задаче (§4, §13.3.6).

Чистая функция без I/O — на вход уже загруженные идентификаторы. У пользователя
нет глобальной роли: роль выводится из его позиции в задаче.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from app.domain.enums import TaskRole


def role_of(
    user_id: UUID,
    *,
    author_id: UUID,
    assignee_id: UUID,
    observer_ids: Iterable[UUID],
) -> TaskRole:
    if author_id == user_id:
        return TaskRole.AUTHOR
    if assignee_id == user_id:
        return TaskRole.ASSIGNEE
    if user_id in set(observer_ids):
        return TaskRole.OBSERVER
    return TaskRole.NONE
