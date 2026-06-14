"""Интеграция: статусный поток на основе проверки (Req 5, task-collaboration).

submit-review (исполнитель) → under_review; review (наблюдатель/админ) →
done | rework; исполнитель не может закрыть задачу сам; админ-override приёмки.
"""

from __future__ import annotations

from tests.factories import auth_header, make_task, make_user


async def test_assignee_submit_then_observer_accepts(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    observer = await make_user(db, "obs@s.ru")
    task = await make_task(db, author, assignee, observers=[observer])
    tid = str(task.id)

    # Исполнитель отправляет на проверку → under_review.
    r = await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    assert r.status_code == 200 and r.json()["status"] == "under_review"

    # Постановщик НЕ приёмщик → 403 на review.
    r = await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "accept"}, headers=auth_header(author)
    )
    assert r.status_code == 403

    # Наблюдатель принимает → done.
    r = await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "accept"}, headers=auth_header(observer)
    )
    assert r.status_code == 200 and r.json()["status"] == "done"


async def test_observer_returns_rework_then_resubmit(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    observer = await make_user(db, "obs@s.ru")
    task = await make_task(db, author, assignee, observers=[observer])
    tid = str(task.id)

    await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    r = await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "rework"}, headers=auth_header(observer)
    )
    assert r.status_code == 200 and r.json()["status"] == "rework"

    # Из доработки исполнитель снова отправляет на проверку.
    r = await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    assert r.status_code == 200 and r.json()["status"] == "under_review"


async def test_assignee_cannot_submit_review_when_not_in_progress(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    observer = await make_user(db, "obs@s.ru")
    task = await make_task(db, author, assignee, observers=[observer])
    tid = str(task.id)

    await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "accept"}, headers=auth_header(observer)
    )
    # done → submit-review недопустим (409 STATUS_CONFLICT).
    r = await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    assert r.status_code == 409


async def test_assignee_cannot_review_own_task(client, db):
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    # Исполнитель не может сам принять — Req 5.4 (никогда не закрывает сам).
    r = await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "accept"}, headers=auth_header(assignee)
    )
    assert r.status_code == 403


async def test_admin_can_decide_review(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(assignee))
    # Администратор без роли по задаче принимает через override.
    r = await client.post(
        f"/api/v1/tasks/{tid}/review", json={"decision": "accept"}, headers=auth_header(admin)
    )
    assert r.status_code == 200 and r.json()["status"] == "done"


async def test_admin_cannot_submit_review(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    author = await make_user(db, "auth@s.ru")
    assignee = await make_user(db, "asg@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    # SUBMIT_REVIEW не имеет admin-override — только исполнитель.
    r = await client.post(f"/api/v1/tasks/{tid}/submit-review", headers=auth_header(admin))
    assert r.status_code == 403
