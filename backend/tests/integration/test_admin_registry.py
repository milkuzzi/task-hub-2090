"""Интеграция: реестр-приглашения, передача администрирования, защита админа.

Модель: единственный администратор; передача администрирования понижает
исходящего админа (его данные сохраняются); админ создаётся консолью/передачей,
а не через реестр. Доступ выдаётся приглашением по e-mail.
"""

from __future__ import annotations

from app.repositories import registry_repo, users_repo
from tests.factories import auth_header, make_user


# --- Реестр: приглашение, без выдачи админа ---------------------------------


async def test_registry_create_invites_inactive_user_and_token(client, db, fake_channels):
    email_fake, _ = fake_channels
    admin = await make_user(db, "admin@s.ru", is_admin=True)

    r = await client.post(
        "/api/v1/admin/registry",
        json={"email": "newbie@s.ru", "fullName": "Новичок"},
        headers=auth_header(admin),
    )
    assert r.status_code == 201
    item = r.json()
    assert item["isAdmin"] is False
    assert item["registered"] is False  # пароль ещё не задан

    # Создана НЕактивная учётка (password_hash=NULL).
    user = await users_repo.get_active_by_email(db, "newbie@s.ru")
    assert user is not None and user.password_hash is None
    # Выслано письмо-приглашение со ссылкой на установку пароля.
    assert email_fake.sent and "token=" in email_fake.sent[-1]["body"]


async def test_registry_create_does_not_grant_admin(client, db, fake_channels):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    # Даже если клиент пришлёт isAdmin=true — поле игнорируется.
    r = await client.post(
        "/api/v1/admin/registry",
        json={"email": "wannabe@s.ru", "isAdmin": True},
        headers=auth_header(admin),
    )
    assert r.status_code == 201
    assert r.json()["isAdmin"] is False
    entry = await registry_repo.get_by_email(db, "wannabe@s.ru")
    assert entry.is_admin is False


# --- Передача администрирования --------------------------------------------


async def test_transfer_admin_self_rejected(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    r = await client.post(
        "/api/v1/admin/transfer-admin",
        json={"email": "admin@s.ru"},
        headers=auth_header(admin),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "SELF_TRANSFER"


async def test_transfer_admin_requires_sole_admin(client, db):
    admin1 = await make_user(db, "admin1@s.ru", is_admin=True)
    await make_user(db, "admin2@s.ru", is_admin=True)  # второй админ → не единственный
    target = await make_user(db, "target@s.ru")
    r = await client.post(
        "/api/v1/admin/transfer-admin",
        json={"email": target.email},
        headers=auth_header(admin1),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "NOT_SOLE_ADMIN"


async def test_transfer_admin_immediate_when_target_active(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    target = await make_user(db, "target@s.ru")  # активный (есть пароль)

    r = await client.post(
        "/api/v1/admin/transfer-admin",
        json={"email": target.email},
        headers=auth_header(admin),
    )
    assert r.status_code == 200
    assert r.json()["completed"] is True

    # Объекты изменены сервисом в рамках той же сессии (identity map) — читаем
    # их напрямую, без принудительного expire (паттерн как в test_user_delete).
    assert target.is_admin is True
    assert admin.is_admin is False and admin.is_deleted is False
    # Реестр синхронизирован.
    assert (await registry_repo.get_by_email(db, target.email)).is_admin is True
    assert (await registry_repo.get_by_email(db, admin.email)).is_admin is False
    assert await users_repo.count_admins(db) == 1


async def test_transfer_admin_deferred_completes_on_password_set(client, db, fake_channels):
    email_fake, _ = fake_channels
    admin = await make_user(db, "admin@s.ru", is_admin=True)

    r = await client.post(
        "/api/v1/admin/transfer-admin",
        json={"email": "incoming@s.ru"},  # новый e-mail, учётки нет
        headers=auth_header(admin),
    )
    assert r.status_code == 200
    assert r.json()["completed"] is False
    assert r.json()["emailSent"] is True

    # До активации исходящий ещё админ (двойной админ — временно).
    assert admin.is_admin is True

    # Входящий активируется по ссылке из письма.
    body = email_fake.sent[-1]["body"]
    token = body.split("token=")[1].split()[0].strip()
    confirm = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "newPassword": "incoming123"},
    )
    assert confirm.status_code == 200

    # Исходящий понижен после активации (объект изменён сервисом в этой сессии).
    incoming = await users_repo.get_active_by_email(db, "incoming@s.ru")
    assert incoming.is_admin is True
    assert admin.is_admin is False  # понижен после активации
    assert await users_repo.count_admins(db) == 1


# --- Защита администратора и самого себя ------------------------------------


async def test_cannot_delete_self(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    r = await client.delete(
        f"/api/v1/admin/users/{admin.id}?confirm=true", headers=auth_header(admin)
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "SELF_DELETION"


async def test_cannot_delete_admin_user(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    other_admin = await make_user(db, "admin2@s.ru", is_admin=True)
    r = await client.delete(
        f"/api/v1/admin/users/{other_admin.id}?confirm=true", headers=auth_header(admin)
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ADMIN_DELETE_FORBIDDEN"


async def test_cannot_remove_admin_registry_entry(client, db):
    admin = await make_user(db, "admin@s.ru", is_admin=True)
    other_admin = await make_user(db, "admin2@s.ru", is_admin=True)
    entry = await registry_repo.get_by_email(db, other_admin.email)
    r = await client.delete(
        f"/api/v1/admin/registry/{entry.id}", headers=auth_header(admin)
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ADMIN_DELETE_FORBIDDEN"
