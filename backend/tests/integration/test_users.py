"""Интеграция: справочник пользователей для выбора исполнителя/наблюдателей."""

from __future__ import annotations

from tests.factories import auth_header, make_user


async def test_list_users_requires_auth(client):
    assert (await client.get("/api/v1/users")).status_code == 401


async def test_list_users_returns_active(client, db):
    me = await make_user(db, "me@s.ru")
    await make_user(db, "colleague@s.ru", display_name="Коллега")
    r = await client.get("/api/v1/users", headers=auth_header(me))
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()}
    assert "me@s.ru" in emails and "colleague@s.ru" in emails
    # каждый элемент — обезличенный публичный профиль
    assert all({"id", "email", "displayName", "isDeleted"} <= set(u) for u in r.json())
