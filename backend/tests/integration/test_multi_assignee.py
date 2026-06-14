"""Интеграция: несколько исполнителей (Req 2, task-collaboration).

Создание с набором исполнителей; вкладка «Я исполнитель» по членству; каждый
исполнитель может отправить на проверку; инварианты (≥1, пересечение с
наблюдателями).
"""

from __future__ import annotations

from datetime import timedelta

from app.core.clock import now
from tests.factories import auth_header, create_task_form, make_task, make_user


def _payload(assignee_ids, **over):
    base = {
        "title": "Совместная задача",
        "dueAt": (now() + timedelta(days=3)).isoformat(),
        "dueMode": "datetime",
        "assigneeIds": [str(a) for a in assignee_ids],
        "observerIds": [],
        "links": [],
    }
    base.update(over)
    return base


async def test_create_with_multiple_assignees(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru", display_name="Первый")
    a2 = await make_user(db, "a2@s.ru", display_name="Второй")
    r = await client.post(
        "/api/v1/tasks", data=create_task_form(_payload([a1.id, a2.id])), headers=auth_header(author)
    )
    assert r.status_code == 201
    names = {a["displayName"] for a in r.json()["assignees"]}
    assert names == {"Первый", "Второй"}


async def test_empty_assignees_rejected(client, db):
    author = await make_user(db, "auth@s.ru")
    r = await client.post(
        "/api/v1/tasks", data=create_task_form(_payload([])), headers=auth_header(author)
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "NO_ASSIGNEES"


async def test_my_assignee_tab_membership(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    outsider = await make_user(db, "out@s.ru")
    task = await make_task(db, author, a1, assignees=[a1, a2])

    # Оба исполнителя видят задачу во вкладке «Я исполнитель».
    for u in (a1, a2):
        lst = await client.get("/api/v1/tasks?role=assignee", headers=auth_header(u))
        assert lst.status_code == 200
        assert any(item["id"] == str(task.id) for item in lst.json()["items"])

    # Посторонний — не видит.
    lst = await client.get("/api/v1/tasks?role=assignee", headers=auth_header(outsider))
    assert all(item["id"] != str(task.id) for item in lst.json()["items"])


async def test_each_assignee_can_submit_review(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    task = await make_task(db, author, a1, assignees=[a1, a2])
    tid = str(task.id)

    # Второй исполнитель тоже имеет право отправить на проверку.
    r = await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(a2))
    assert r.status_code == 200 and r.json()["status"] == "under_review"


async def test_observer_cannot_overlap_any_assignee(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    payload = _payload([a1.id, a2.id], observerIds=[str(a2.id)])
    r = await client.post(
        "/api/v1/tasks", data=create_task_form(payload), headers=auth_header(author)
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "ASSIGNEE_AS_OBSERVER"


async def test_reassign_to_multiple(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    a3 = await make_user(db, "a3@s.ru")
    task = await make_task(db, author, a1)
    tid = str(task.id)

    upd = await client.put(
        f"/api/v1/tasks/{tid}",
        json={"assigneeIds": [str(a2.id), str(a3.id)]},
        headers=auth_header(author),
    )
    assert upd.status_code == 200
    ids = {a["id"] for a in upd.json()["assignees"]}
    assert ids == {str(a2.id), str(a3.id)}
