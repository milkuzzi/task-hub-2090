"""Интеграция: on-site уведомления — создание, счётчик, прочтение, доработка (§6)."""

from __future__ import annotations

from tests.factories import auth_header, make_task, make_user


async def test_chat_creates_notification_for_other_assignees_not_author(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    task = await make_task(db, author, a1, assignees=[a1, a2])
    tid = str(task.id)

    # a1 пишет сообщение → уведомление получает a2, но не сам a1.
    r = await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "hi"}, headers=auth_header(a1)
    )
    assert r.status_code == 201

    r = await client.get("/api/v1/notifications/unread-count", headers=auth_header(a2))
    assert r.json()["unread"] == 1
    r = await client.get("/api/v1/notifications/unread-count", headers=auth_header(a1))
    assert r.json()["unread"] == 0

    r = await client.get("/api/v1/notifications", headers=auth_header(a2))
    body = r.json()
    assert body["unread"] == 1
    assert body["items"][0]["kind"] == "chat_message"
    assert body["items"][0]["taskId"] == tid


async def test_author_chat_message_does_not_notify_author(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    # Постановщик пишет — исполнитель получает уведомление, постановщик нет.
    await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "hi"}, headers=auth_header(author)
    )
    r = await client.get("/api/v1/notifications/unread-count", headers=auth_header(assignee))
    assert r.json()["unread"] == 1
    r = await client.get("/api/v1/notifications/unread-count", headers=auth_header(author))
    assert r.json()["unread"] == 0


async def test_mark_read_is_idempotent(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    task = await make_task(db, author, a1, assignees=[a1, a2])
    tid = str(task.id)
    await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "hi"}, headers=auth_header(a1)
    )

    # Первая пометка — помечает 1; повторная — 0; счётчик не уходит ниже 0.
    r = await client.post("/api/v1/notifications/read", json={}, headers=auth_header(a2))
    assert r.json() == {"marked": 1, "unread": 0}
    r = await client.post("/api/v1/notifications/read", json={}, headers=auth_header(a2))
    assert r.json() == {"marked": 0, "unread": 0}


async def test_mark_read_by_ids(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    task = await make_task(db, author, a1, assignees=[a1, a2])
    tid = str(task.id)
    await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "hi"}, headers=auth_header(a1)
    )
    r = await client.get("/api/v1/notifications", headers=auth_header(a2))
    notif_id = r.json()["items"][0]["id"]

    r = await client.post(
        "/api/v1/notifications/read", json={"ids": [notif_id]}, headers=auth_header(a2)
    )
    assert r.json()["marked"] == 1 and r.json()["unread"] == 0


async def test_mark_read_by_task_on_open(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    task = await make_task(db, author, a1, assignees=[a1, a2])
    tid = str(task.id)
    await client.post(
        f"/api/v1/tasks/{tid}/messages", json={"body": "hi"}, headers=auth_header(a1)
    )

    r = await client.post(
        "/api/v1/notifications/read", json={"taskId": tid}, headers=auth_header(a2)
    )
    assert r.json()["unread"] == 0


async def test_rework_creates_notifications_for_assignees(client, db):
    author = await make_user(db, "auth@s.ru")
    a1 = await make_user(db, "a1@s.ru")
    a2 = await make_user(db, "a2@s.ru")
    observer = await make_user(db, "obs@s.ru")
    task = await make_task(db, author, a1, observers=[observer], assignees=[a1, a2])
    tid = str(task.id)

    await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(a1))
    r = await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "rework"}, headers=auth_header(observer)
    )
    assert r.status_code == 200 and r.json()["status"] == "rework"

    # Оба исполнителя получили уведомление о доработке.
    for asg in (a1, a2):
        r = await client.get("/api/v1/notifications", headers=auth_header(asg))
        body = r.json()
        assert body["unread"] == 1
        assert body["items"][0]["kind"] == "task_rework"
