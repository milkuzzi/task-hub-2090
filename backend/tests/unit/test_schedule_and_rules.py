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
from app.domain.status import validate_transition

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
    # отчёт/готовность — только исполнитель
    for action in (Action.ADD_REPORT, Action.MARK_READY):
        assert can(action, TaskRole.ASSIGNEE)
        assert not can(action, TaskRole.AUTHOR)
        assert not can(action, TaskRole.OBSERVER)
    # просмотр/экспорт — все три роли
    for action in (Action.VIEW, Action.EXPORT):
        assert all(can(action, r) for r in (TaskRole.AUTHOR, TaskRole.ASSIGNEE, TaskRole.OBSERVER))
    # NONE не может ничего
    assert all(not can(a, TaskRole.NONE) for a in ALLOWED)


def test_authorize_raises_403():
    with pytest.raises(AppError) as exc:
        authorize(Action.CHANGE_STATUS, TaskRole.ASSIGNEE)
    assert exc.value.status_code == 403


# --- Статус-машина ---


def test_status_transitions():
    validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE)
    validate_transition(TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED)
    validate_transition(TaskStatus.DONE, TaskStatus.IN_PROGRESS)
    with pytest.raises(AppError):
        validate_transition(TaskStatus.CANCELLED, TaskStatus.DONE)


# --- Инварианты (§13.7.3 З) ---


def test_observers_limit_and_dedup():
    assignee = uuid.uuid4()
    author = uuid.uuid4()
    ids = [uuid.uuid4() for _ in range(6)]
    with pytest.raises(AppError):
        invariants.validate_observers(ids, assignee_id=assignee, author_id=author)
    # дедуп: 5 уникальных из дублей — ок
    dup = [ids[0]] * 3 + [ids[1], ids[2]]
    assert len(invariants.validate_observers(dup, assignee_id=assignee, author_id=author)) == 3


def test_observer_cannot_be_assignee_or_author():
    assignee = uuid.uuid4()
    author = uuid.uuid4()
    with pytest.raises(AppError):
        invariants.validate_observers([assignee], assignee_id=assignee, author_id=author)
    with pytest.raises(AppError):
        invariants.validate_observers([author], assignee_id=assignee, author_id=author)


def test_title_and_assignee_required():
    with pytest.raises(AppError):
        invariants.validate_title("   ")
    with pytest.raises(AppError):
        invariants.validate_assignee(None)
    assert invariants.validate_title("  Привет  ") == "Привет"
