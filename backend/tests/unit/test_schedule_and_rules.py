"""Юнит: график событий, матрица прав, статус-машина, инварианты (§13.7.3 А/Д/З)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.core.errors import AppError
from app.domain import invariants
from app.domain.enums import Action, NotifyEvent, TaskRole, TaskStatus
from app.domain.notifications.schedule import due_event_for
from app.domain.permissions import ALLOWED, authorize, can
from app.domain.status import is_open, validate_transition

# --- График (§13.7.3 Д) ---


def test_due_event_for():
    dl = date(2026, 6, 11)
    assert due_event_for(date(2026, 6, 10), dl) == NotifyEvent.DUE_TOMORROW
    assert due_event_for(date(2026, 6, 11), dl) == NotifyEvent.DUE_TODAY
    assert due_event_for(date(2026, 6, 12), dl) == NotifyEvent.OVERDUE_DAILY
    assert due_event_for(date(2026, 6, 9), dl) is None


# --- Матрица прав (§6, §13.7.3 А) ---


def test_permission_matrix_cells():
    # постановщик: всё по своей задаче
    for action in (Action.EDIT_FIELDS, Action.DELETE_TASK, Action.CHANGE_STATUS):
        assert can(action, TaskRole.AUTHOR)
        assert not can(action, TaskRole.ASSIGNEE)
        assert not can(action, TaskRole.OBSERVER)
    # отчёт/готовность/«готово к проверке» — только исполнитель
    for action in (Action.ADD_REPORT, Action.MARK_READY, Action.SUBMIT_REVIEW):
        assert can(action, TaskRole.ASSIGNEE)
        assert not can(action, TaskRole.AUTHOR)
        assert not can(action, TaskRole.OBSERVER)
    # приёмка — наблюдатель (не исполнитель, не постановщик без override)
    assert can(Action.DECIDE_REVIEW, TaskRole.OBSERVER)
    assert not can(Action.DECIDE_REVIEW, TaskRole.ASSIGNEE)
    assert not can(Action.DECIDE_REVIEW, TaskRole.AUTHOR)
    # просмотр/экспорт — все три роли
    for action in (Action.VIEW, Action.EXPORT):
        assert all(can(action, r) for r in (TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER))
    # NONE не может ничего
    assert all(not can(a, TaskRole.NONE) for a in ALLOWED)


def test_authorize_raises_403():
    with pytest.raises(AppError) as exc:
        authorize(Action.CHANGE_STATUS, TaskRole.ASSIGNEE)
    assert exc.value.status_code == 403


def test_admin_override_grants_and_excludes_submit_review():
    # Админ получает override на просмотр/правку/приёмку и т.п. без роли по задаче.
    for action in (
        Action.VIEW,
        Action.EXPORT,
        Action.EDIT_FIELDS,
        Action.DELETE_TASK,
        Action.CHANGE_STATUS,
        Action.DECIDE_REVIEW,
    ):
        authorize(action, TaskRole.NONE, is_admin=True)  # не бросает
    # SUBMIT_REVIEW — только исполнитель, даже админу нельзя.
    with pytest.raises(AppError):
        authorize(Action.SUBMIT_REVIEW, TaskRole.NONE, is_admin=True)


# --- Статус-машина (поток на основе проверки) ---


def test_status_transitions():
    # Исполнитель отправляет на проверку, приёмщик принимает/возвращает.
    validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.UNDER_REVIEW)
    validate_transition(TaskStatus.UNDER_REVIEW, TaskStatus.DONE)
    validate_transition(TaskStatus.UNDER_REVIEW, TaskStatus.REWORK)
    validate_transition(TaskStatus.REWORK, TaskStatus.UNDER_REVIEW)
    # Отмена из любого открытого состояния и переоткрытие из закрытого.
    validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED)
    validate_transition(TaskStatus.DONE, TaskStatus.IN_PROGRESS)
    validate_transition(TaskStatus.CANCELLED, TaskStatus.IN_PROGRESS)
    # Прямой in_progress→done запрещён (только через проверку).
    with pytest.raises(AppError):
        validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE)
    with pytest.raises(AppError):
        validate_transition(TaskStatus.CANCELLED, TaskStatus.DONE)


def test_is_open_includes_review_states():
    assert is_open(TaskStatus.IN_PROGRESS)
    assert is_open(TaskStatus.UNDER_REVIEW)
    assert is_open(TaskStatus.REWORK)
    assert not is_open(TaskStatus.DONE)
    assert not is_open(TaskStatus.CANCELLED)


# --- Инварианты (§13.7.3 З) ---


def test_observers_limit_and_dedup():
    assignee = uuid.uuid4()
    author = uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(6)]
    with pytest.raises(AppError):
        invariants.validate_observers(ids, assignee_ids=[assignee], author_id=author)
    # дедуп: 5 уникальных из дублей — ок
    dup = [ids[0]] * 3 + [ids[1], ids[2]]
    assert len(invariants.validate_observers(dup, assignee_ids=[assignee], author_id=author)) == 3


def test_observer_cannot_be_assignee_or_author():
    assignee = uuid.uuid4()
    author = uuid.uuid4()
    with pytest.raises(AppError):
        invariants.validate_observers([assignee], assignee_ids=[assignee], author_id=author)
    with pytest.raises(AppError):
        invariants.validate_observers([author], assignee_ids=[assignee], author_id=author)


def test_assignees_required_and_deduped():
    a = uuid.uuid4()
    b = uuid.uuid4()
    with pytest.raises(AppError):
        invariants.validate_assignees([])
    # дубли убираются, порядок сохраняется
    assert invariants.validate_assignees([a, a, b]) == [a, b]


def test_title_required():
    with pytest.raises(AppError):
        invariants.validate_title("   ")
    assert invariants.validate_title("  Привет  ") == "Привет"
