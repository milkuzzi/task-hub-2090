"""Интеграция: вход, блокировка доступа, сброс пароля, приглашения (§13.7.3 Ж/Е).

Публичная регистрация удалена — доступ выдаётся только администратором через
реестр (приглашение по e-mail). Активация = установка пароля по ссылке.
"""

from __future__ import annotations

from app.repositories import registry_repo, users_repo
from app.schemas.admin import RegistryCreateIn
from app.services import registry_service
from tests.factories import auth_header, make_user


async def test_register_endpoint_removed(client):
    # Публичной регистрации больше нет — маршрут отсутствует.
    r = await client.post(
        "/api/v1/auth/register", json={"email": "stranger@nowhere.ru", "password": "password123"}
    )
    assert r.status_code in (404, 405)


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


async def test_login_blocked_until_password_set(client, db, fake_channels):
    """Приглашённый (НЕактивный, password_hash=NULL) не может войти, пока не задаст пароль."""
    email_fake, _ = fake_channels
    # Приглашаем пользователя через реестр → создаётся неактивная учётка + письмо.
    await registry_service.create_entry(db, RegistryCreateIn(email="invited@school.ru"))

    user = await users_repo.get_active_by_email(db, "invited@school.ru")
    assert user is not None and user.password_hash is None

    # Вход невозможен до установки пароля.
    blocked = await client.post(
        "/api/v1/auth/login", json={"email": "invited@school.ru", "password": "whatever1"}
    )
    assert blocked.status_code == 401

    # Активация по ссылке из письма-приглашения.
    body = email_fake.sent[-1]["body"]
    token = body.split("token=")[1].split()[0].strip()
    confirm = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "newPassword": "freshpass1"},
    )
    assert confirm.status_code == 200

    ok = await client.post(
        "/api/v1/auth/login", json={"email": "invited@school.ru", "password": "freshpass1"}
    )
    assert ok.status_code == 200


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
