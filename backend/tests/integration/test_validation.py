"""Интеграция: серверная валидация инвариантов (§13.7.3 З)."""

from __future__ import annotations

from datetime import timedelta

from app.core.clock import now
from tests.factories import auth_header, make_user


def _payload(assignee_id, **over):
    base = {
        "title": "Задача",
        "dueAt": (now() + timedelta(days=1)).isoformat(),
        "dueMode": "datetime",
        "assigneeId": str(assignee_id),
        "observerIds": [],
        "links": [],
    }
    base.update(over)
    return base


async def test_more_than_five_observers_rejected(client, db):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    observers = [await make_user(db, f"o{i}@s.ru") for i in range(6)]
    payload = _payload(assignee.id, observerIds=[str(o.id) for o in observers])
    r = await client.post("/api/v1/tasks", json=payload, headers=auth_header(author))
    assert r.status_code == 422


async def test_title_required(client, db):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    payload = _payload(assignee.id, title="   ")
    r = await client.post("/api/v1/tasks", json=payload, headers=auth_header(author))
    assert r.status_code == 422


async def test_assignee_must_exist_and_be_listed(client, db):
    import uuid

    author = await make_user(db, "a@s.ru")
    payload = _payload(uuid.uuid4())  # несуществующий исполнитель
    r = await client.post("/api/v1/tasks", json=payload, headers=auth_header(author))
    assert r.status_code == 422


async def test_observer_cannot_equal_assignee(client, db):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    payload = _payload(assignee.id, observerIds=[str(assignee.id)])
    r = await client.post("/api/v1/tasks", json=payload, headers=auth_header(author))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "ASSIGNEE_AS_OBSERVER"


async def test_author_cannot_be_observer(client, db):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    payload = _payload(assignee.id, observerIds=[str(author.id)])
    r = await client.post("/api/v1/tasks", json=payload, headers=auth_header(author))
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "SELF_AS_OBSERVER"
    assert body["error"]["message"] == "Нельзя добавить себя в наблюдатели."


async def test_valid_task_creates_with_seq_and_code(client, db):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    r = await client.post("/api/v1/tasks", json=_payload(assignee.id), headers=auth_header(author))
    assert r.status_code == 201
    data = r.json()
    assert data["seqNo"] >= 1
    assert len(data["code"]) == 6 and data["code"].isdigit()
    assert data["status"] == "in_progress"
    assert data["isOverdue"] is False
