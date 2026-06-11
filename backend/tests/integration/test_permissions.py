"""Интеграция: матрица прав через API, видимость 404-не-403 (§13.7.3 А)."""

from __future__ import annotations

from tests.factories import auth_header, make_task, make_user


async def test_assignee_cannot_edit_status_delete(client, db):
    author = await make_user(db, "author@s.ru")
    assignee = await make_user(db, "assignee@s.ru")
    task = await make_task(db, author, assignee, title="Исходное")
    tid = str(task.id)
    h = auth_header(assignee)

    assert (await client.put(f"/api/v1/tasks/{tid}", json={"title": "взлом"}, headers=h)).status_code == 403
    assert (
        await client.patch(f"/api/v1/tasks/{tid}/status", json={"status": "done"}, headers=h)
    ).status_code == 403
    assert (await client.delete(f"/api/v1/tasks/{tid}", headers=h)).status_code == 403

    # состояние не изменилось
    view = await client.get(f"/api/v1/tasks/{tid}", headers=auth_header(author))
    assert view.json()["title"] == "Исходное"
    assert view.json()["status"] == "in_progress"


async def test_observer_visibility_and_privacy(client, db):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    observer = await make_user(db, "obs@s.ru")
    outsider = await make_user(db, "out@s.ru")

    own = await make_task(db, author, assignee, observers=[observer])
    foreign = await make_task(db, author, assignee)

    # наблюдатель видит свою задачу
    assert (await client.get(f"/api/v1/tasks/{own.id}", headers=auth_header(observer))).status_code == 200
    # чужую — 404 (не раскрываем существование)
    assert (
        await client.get(f"/api/v1/tasks/{foreign.id}", headers=auth_header(observer))
    ).status_code == 404
    # посторонний — 404
    assert (
        await client.get(f"/api/v1/tasks/{own.id}", headers=auth_header(outsider))
    ).status_code == 404
    # наблюдатель не может мутировать
    assert (
        await client.patch(
            f"/api/v1/tasks/{own.id}/status", json={"status": "done"}, headers=auth_header(observer)
        )
    ).status_code == 403


async def test_report_only_by_assignee(client, db):
    author = await make_user(db, "a2@s.ru")
    assignee = await make_user(db, "b2@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)

    # постановщик не может писать отчёт
    assert (
        await client.post(f"/api/v1/tasks/{tid}/report", json={"text": "x"}, headers=auth_header(author))
    ).status_code == 403
    # исполнитель — может
    assert (
        await client.post(
            f"/api/v1/tasks/{tid}/report", json={"text": "сделано"}, headers=auth_header(assignee)
        )
    ).status_code == 201
    # mark-ready только исполнитель
    assert (
        await client.post(f"/api/v1/tasks/{tid}/mark-ready", json={}, headers=auth_header(author))
    ).status_code == 403
    ready = await client.post(f"/api/v1/tasks/{tid}/mark-ready", json={}, headers=auth_header(assignee))
    assert ready.status_code == 200 and ready.json()["ready"] is True
    # повторно → 409
    assert (
        await client.post(f"/api/v1/tasks/{tid}/mark-ready", json={}, headers=auth_header(assignee))
    ).status_code == 409


async def test_author_full_crud_and_ready_indicator(client, db):
    author = await make_user(db, "a3@s.ru")
    assignee = await make_user(db, "b3@s.ru")
    task = await make_task(db, author, assignee)
    tid = str(task.id)
    ha = auth_header(author)

    upd = await client.put(f"/api/v1/tasks/{tid}", json={"title": "Новое название"}, headers=ha)
    assert upd.status_code == 200 and upd.json()["title"] == "Новое название"

    # исполнитель отметил готовность → в карточке у постановщика виден индикатор
    await client.post(f"/api/v1/tasks/{tid}/mark-ready", json={}, headers=auth_header(assignee))
    card = await client.get(f"/api/v1/tasks/{tid}", headers=ha)
    assert card.json()["assigneeMarkedReady"] is True

    st = await client.patch(f"/api/v1/tasks/{tid}/status", json={"status": "done"}, headers=ha)
    assert st.status_code == 200 and st.json()["status"] == "done"
    assert (await client.delete(f"/api/v1/tasks/{tid}", headers=ha)).status_code == 200


async def test_search_scope_limited_to_visibility(client, db):
    author = await make_user(db, "a4@s.ru")
    assignee = await make_user(db, "b4@s.ru")
    outsider = await make_user(db, "c4@s.ru")
    task = await make_task(db, author, assignee)
    code = f"{task.code6:06d}"

    assert (
        await client.get(f"/api/v1/tasks/search?code={code}", headers=auth_header(assignee))
    ).status_code == 200
    assert (
        await client.get(f"/api/v1/tasks/search?code={code}", headers=auth_header(outsider))
    ).status_code == 404
    # невалидный код
    assert (
        await client.get("/api/v1/tasks/search?code=12", headers=auth_header(assignee))
    ).status_code == 422
