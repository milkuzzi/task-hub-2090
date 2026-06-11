"""Интеграция: регистрация, вход, блокировка доступа, сброс пароля (§13.7.3 Ж/Е)."""

from __future__ import annotations

from app.core.errors import NO_ACCESS_MESSAGE
from app.models import EmailRegistry
from app.repositories import registry_repo
from tests.factories import auth_header, make_user


async def test_register_refusal_exact_phrase(client):
    r = await client.post(
        "/api/v1/auth/register", json={"email": "stranger@nowhere.ru", "password": "password123"}
    )
    assert r.status_code == 403
    body = r.json()
    assert body["error"]["code"] == "EMAIL_NOT_IN_REGISTRY"
    # дословно, включая регистр и точку
    assert body["error"]["message"] == NO_ACCESS_MESSAGE
    assert body["error"]["message"] == "Извините, у вас нет доступа к сервису."


async def test_register_success_when_listed(client, db):
    db.add(EmailRegistry(email="teacher@school.ru"))
    await db.flush()
    r = await client.post(
        "/api/v1/auth/register", json={"email": "teacher@school.ru", "password": "password123"}
    )
    assert r.status_code == 200
    assert r.json()["user"]["email"].lower() == "teacher@school.ru"
    # повторная регистрация → конфликт
    r2 = await client.post(
        "/api/v1/auth/register", json={"email": "teacher@school.ru", "password": "password123"}
    )
    assert r2.status_code == 409


async def test_login_and_me(client, db):
    await make_user(db, "u@school.ru")
    r = await client.post(
        "/api/v1/auth/login", json={"email": "u@school.ru", "password": "password123"}
    )
    assert r.status_code == 200
    token = r.json()["accessToken"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"].lower() == "u@school.ru"
    # неверный пароль
    bad = await client.post(
        "/api/v1/auth/login", json={"email": "u@school.ru", "password": "wrong"}
    )
    assert bad.status_code == 401


async def test_removed_from_registry_blocks_access_and_login(client, db):
    user = await make_user(db, "gone@school.ru")
    headers = auth_header(user)
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200

    entry = await registry_repo.get_by_email(db, "gone@school.ru")
    await registry_repo.delete(db, entry)
    await db.flush()

    revoked = await client.get("/api/v1/auth/me", headers=headers)
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "REGISTRY_ACCESS_REVOKED"

    relogin = await client.post(
        "/api/v1/auth/login", json={"email": "gone@school.ru", "password": "password123"}
    )
    assert relogin.status_code == 401


async def test_password_reset_flow(client, db, fake_channels):
    email_fake, _ = fake_channels
    await make_user(db, "reset@school.ru")
    r = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset@school.ru"}
    )
    assert r.status_code == 200
    # извлекаем сырой токен из письма (фейк-канал)
    body = email_fake.sent[-1]["body"]
    token = body.split("token=")[1].split()[0].strip()

    confirm = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "newPassword": "brandnew123"},
    )
    assert confirm.status_code == 200

    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "reset@school.ru", "password": "password123"}
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/v1/auth/login", json={"email": "reset@school.ru", "password": "brandnew123"}
        )
    ).status_code == 200
    # повторное использование токена не проходит
    reuse = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "newPassword": "another123"},
    )
    assert reuse.status_code == 400


async def test_reset_request_always_ok_for_unknown_email(client):
    r = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "unknown@school.ru"}
    )
    assert r.status_code == 200  # не раскрываем наличие e-mail
