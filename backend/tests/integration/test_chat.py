"""Интеграция: чат задачи — права, персистентность, валидация, WS-доставка (§4)."""

from __future__ import annotations

from datetime import timedelta

from app.api.deps import TaskContext
from app.core.clock import now
from app.core.config import settings
from app.domain.enums import TaskRole
from app.models import TaskMessage
from app.realtime.manager import manager
from app.repositories import tasks_repo
from app.services import chat_service
from tests.factories import auth_header, current_of, make_task, make_user
from tests.fakes import FakeSocket


async def test_assignee_can_post_and_message_persists(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "Привет"}, headers=auth_header(assignee)
    )
    assert r.status_code == 201
    body = r.json()
    assert body["body"] == "Привет"
    assert body["authorId"] == str(assignee.id)
    assert body["authorName"] == assignee.display_name

    # Сообщение читается через историю.
    r = await client.get(f"/api/v1/tasks/{tid}/messages", headers=auth_header(author))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["body"] == "Привет"


async def test_author_and_observer_can_post(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    observer = await make_user(db, "obs@s.ru")
    task = await make_task(db, author, assignee, observers=[observer])
    tid = str(task.id)

    for who in (author, observer):
        r = await client.post(
            f"/api/v1/tasks/{tid}/messages", json={"body": "ok"}, headers=auth_header(who)
        )
        assert r.status_code == 201


async def test_outsider_gets_404_on_chat(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    outsider = await make_user(db, "out@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "hi"}, headers=auth_header(outsider)
    )
    assert r.status_code == 404
    r = await client.get(f"/api/v1/tasks/{tid}/messages", headers=auth_header(outsider))
    assert r.status_code == 404


async def test_admin_can_post_via_override(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "от админа"}, headers=auth_header(admin)
    )
    assert r.status_code == 201


async def test_empty_body_rejected(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    # Pydantic min_length=1 → 422 для пустой строки.
    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": ""}, headers=auth_header(assignee)
    )
    assert r.status_code == 422


async def test_whitespace_only_body_rejected(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    # Только пробелы → пусто после strip → 422 (доменная валидация).
    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "   "}, headers=auth_header(assignee)
    )
    assert r.status_code == 422


async def test_too_long_body_rejected(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    too_long = "я" * (settings.max_message_len + 1)
    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": too_long}, headers=auth_header(assignee)
    )
    assert r.status_code == 422


async def test_pagination_after_cursor(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    # Вставляем сообщения с РАЗНЫМИ created_at напрямую: в одном тестовом
    # транзакционном контексте server-side now() одинаков для всех вставок,
    # поэтому задаём метки времени явно (в проде каждое сообщение — свой коммит).
    base = now()
    for i in range(3):
        db.add(
            TaskMessage(
                task_id=task.id,
                author_id=assignee.id,
                body=f"m{i}",
                created_at=base + timedelta(seconds=i),
            )
        )
    await db.commit()

    r = await client.get(
        f"/api/v1/tasks/{tid}/messages", params={"limit": 2}, headers=auth_header(author)
    )
    page1 = r.json()
    assert [m["body"] for m in page1["items"]] == ["m0", "m1"]
    assert page1["nextAfter"] is not None

    r = await client.get(
        f"/api/v1/tasks/{tid}/messages",
        params={"limit": 2, "after": page1["nextAfter"]},
        headers=auth_header(author),
    )
    page2 = r.json()
    assert [m["body"] for m in page2["items"]] == ["m2"]


async def test_post_message_broadcasts_to_connected_participants(db):
    """chat_service рассылает chat участникам и notification — исполнителям ≠ автору."""
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    observer = await make_user(db, "obs@s.ru")
    task = await make_task(db, author, a1, observers=[observer], assignees=[a1, a2])
    task = await tasks_repo.get_full(db, task.id)

    # a1 пишет сообщение; контекст — роль исполнителя.
    ctx = TaskContext(task=task, user=current_of(a1), role=TaskRole.ASSIGNEE)

    sockets = {
        author.id: FakeSocket(),
        a1.id: FakeSocket(),
        a2.id: FakeSocket(),
        observer.id: FakeSocket(),
    }
    for uid, ws in sockets.items():
        await manager.connect(uid, ws)
    try:
        await chat_service.post_message(db, ctx, "всем привет")
    finally:
        for uid, ws in sockets.items():
            await manager.disconnect(uid, ws)

    # chat пришёл всем участникам (включая автора).
    for uid in (author.id, a1.id, a2.id, observer.id):
        assert "chat" in sockets[uid].types(), uid

    # notification пришёл только другому исполнителю (a2), не автору сообщения (a1).
    assert "notification" in sockets[a2.id].types()
    assert "notification" not in sockets[a1.id].types()
    assert "notification" not in sockets[author.id].types()
    assert "notification" not in sockets[observer.id].types()
