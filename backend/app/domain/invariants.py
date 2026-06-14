"""Серверная проверка инвариантов задачи (§5, §11, §13.3.7).

Чистые проверки (без I/O). Проверки членства в реестре — в сервисном слое
(нужен доступ к БД). Pydantic даёт первый форматный барьер; эти доменные
проверки обязательны — чтобы инвариант нельзя было обойти кастомным запросом.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.core.config import settings
from app.core.errors import (
    assignee_as_observer,
    no_assignees,
    self_as_observer,
    validation_error,
)


def validate_title(title: str) -> str:
    title = (title or "").strip()
    if not title:
        raise validation_error([{"field": "title", "message": "Название обязательно."}])
    return title


def validate_observers(
    observer_ids: Sequence[UUID],
    *,
    assignee_ids: Sequence[UUID],
    author_id: UUID,
) -> list[UUID]:
    """≤MAX наблюдателей, без дублей, наблюдатель ≠ исполнитель/постановщик."""
    deduped = list(dict.fromkeys(observer_ids))  # сохраняем порядок, убираем дубли
    if len(deduped) > settings.max_observers:
        raise validation_error(
            [{"field": "observers", "message": f"Не более {settings.max_observers} наблюдателей."}]
        )
    # Доменные ошибки 400 с понятным текстом верхнего уровня (фронт показывает
    # error.message): «себя нельзя в наблюдатели», «исполнитель ≠ наблюдатель».
    if author_id in deduped:
        raise self_as_observer()
    assignee_set = set(assignee_ids)
    if any(oid in assignee_set for oid in deduped):
        raise assignee_as_observer()
    return deduped


def validate_assignees(assignee_ids: Sequence[UUID]) -> list[UUID]:
    """Хотя бы один исполнитель; дубли убираются, порядок сохраняется."""
    deduped = list(dict.fromkeys(assignee_ids or []))
    if not deduped:
        raise no_assignees()
    return deduped
