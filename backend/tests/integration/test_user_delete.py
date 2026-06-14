"""Интеграция: удаление пользователя и архива, tombstone, переназначение (§13.7.3 Е)."""

from __future__ import annotations

from app.repositories import users_repo
from tests.factories import auth_header, make_task, make_user


async def test_delete_user_cascades_and_flags(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    victim = await make_user(db, "victim@s.ru", display_name="Жертва")
    other = await make_user(db, "other@s.ru")
    other_assignee = await make_user(db, "asg2@s.ru")

    authored = await make_task(db, victim, other)  # victim — постановщик
    foreign = await make_task(db, other, victim)  # victim — исполнитель в чужой задаче
    observed = await make_task(db, other, other_assignee, observers=[victim])  # victim — наблюдатель

    # не-админ не может удалять
    assert (
        await client.delete(f"/api/v1/admin/users/{victim.id}?confirm=true", headers=auth_header(other))
    ).status_code == 403
    # без confirm — 400
    assert (
        await client.delete(f"/api/v1/admin/users/{victim.id}", headers=auth_header(admin))
    ).status_code == 400

    resp = await client.delete(
        f"/api/v1/admin/users/{victim.id}?confirm=true", headers=auth_header(admin)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deletedTasksAsAuthor"] == 1
    assert body["flaggedForReassignment"] == 1

    # учётка обезличена, вход заблокирован
    tomb = await users_repo.get_by_id(db, victim.id)
    assert tomb.is_deleted is True
    assert tomb.display_name == "Пользователь удалён"
    assert tomb.email != "victim@s.ru"
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "victim@s.ru", "password": "password123"}
        )
    ).status_code == 401

    # собственная задача victim удалена
    assert (
        await client.get(f"/api/v1/tasks/{authored.id}", headers=auth_header(other))
    ).status_code == 404

    # чужая задача с victim-исполнителем помечена к переназначению, исполнитель обезличен
    fcard = await client.get(f"/api/v1/tasks/{foreign.id}", headers=auth_header(other))
    assert fcard.status_code == 200
    assert fcard.json()["needsReassignment"] is True
    assert fcard.json()["assignees"][0]["displayName"] == "Пользователь удалён"
    assert fcard.json()["assignees"][0]["isDeleted"] is True

    # участие наблюдателя обезличено
    ocard = await client.get(f"/api/v1/tasks/{observed.id}", headers=auth_header(other))
    assert ocard.json()["observers"][0]["displayName"] == "Пользователь удалён"


async def test_reassignment_clears_flag(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    victim = await make_user(db, "victim@s.ru")
    author = await make_user(db, "author@s.ru")
    replacement = await make_user(db, "newasg@s.ru")
    foreign = await make_task(db, author, victim)

    await client.delete(f"/api/v1/admin/users/{victim.id}?confirm=true", headers=auth_header(admin))
    # автор переназначает исполнителя → флаг снимается
    upd = await client.put(
        f"/api/v1/tasks/{foreign.id}",
        json={"assigneeIds": [str(replacement.id)]},
        headers=auth_header(author),
    )
    assert upd.status_code == 200
    assert upd.json()["needsReassignment"] is False
    assert upd.json()["assignees"][0]["displayName"] == "newasg"
