"""Интеграция: профиль пользователя — отображаемое имя, контакт MAX и аватар (§8).

Покрывает: GET/PATCH /users/me (установка/очистка/валидация MAX и имени), загрузку
валидного PNG/JPEG (хранение, hasAvatar, раздача байтов с корректным content-type),
отклонение не-изображений (magic-byte проверка) и превышения размера, удаление
аватара (GET → 404), требование аутентификации на чужой аватар.
"""

from __future__ import annotations

import struct
import zlib

import pytest

import app.storage.base as storage_base
from app.storage.base import LocalStorage
from tests.factories import auth_header, make_user


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Хранилище в tmp-каталоге вместо тома /data, чтобы тест не писал на боевой путь."""
    monkeypatch.setattr(storage_base, "_storage", LocalStorage(root=str(tmp_path)))
    yield
    monkeypatch.setattr(storage_base, "_storage", None)


# --- Минимальные валидные изображения для проверки magic bytes ---


def _png_bytes() -> bytes:
    """Корректный 1x1 PNG (сигнатура + IHDR + IDAT + IEND)."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"  # один пиксель (фильтр 0 + RGB)
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _jpeg_bytes() -> bytes:
    """Минимальный JPEG: SOI + APP0(JFIF) + EOI (достаточно для magic-byte проверки)."""
    soi = b"\xff\xd8\xff"
    app0 = b"\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    eoi = b"\xff\xd9"
    return soi + app0 + eoi


def _webp_bytes() -> bytes:
    """RIFF-контейнер с формой WEBP."""
    payload = b"VP8 " + b"\x00" * 16
    return b"RIFF" + struct.pack("<I", 4 + len(payload)) + b"WEBP" + payload


# --- GET / PATCH /users/me ---


async def test_get_me_returns_profile(client, db):
    user = await make_user(db, "me@s.ru", display_name="Иван Петров", max_contact="@ivan")
    r = await client.get("/api/v1/users/me", headers=auth_header(user))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@s.ru"
    assert body["displayName"] == "Иван Петров"
    assert body["isAdmin"] is False
    assert body["maxContact"] == "@ivan"
    assert body["hasAvatar"] is False


async def test_get_me_requires_auth(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401


async def test_patch_me_sets_max_contact(client, db):
    user = await make_user(db, "me@s.ru")
    r = await client.patch(
        "/api/v1/users/me", headers=auth_header(user), json={"maxContact": "  +79990001122 "}
    )
    assert r.status_code == 200
    assert r.json()["maxContact"] == "+79990001122"  # обрезка пробелов
    # Перечитываем — значение сохранилось в реестре.
    again = await client.get("/api/v1/users/me", headers=auth_header(user))
    assert again.json()["maxContact"] == "+79990001122"


async def test_patch_me_clears_max_contact_with_empty_string(client, db):
    user = await make_user(db, "me@s.ru", max_contact="@old")
    r = await client.patch(
        "/api/v1/users/me", headers=auth_header(user), json={"maxContact": ""}
    )
    assert r.status_code == 200
    assert r.json()["maxContact"] is None


async def test_patch_me_validates_max_contact_length(client, db):
    user = await make_user(db, "me@s.ru")
    r = await client.patch(
        "/api/v1/users/me", headers=auth_header(user), json={"maxContact": "x" * 200}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_patch_me_updates_display_name(client, db):
    user = await make_user(db, "me@s.ru", display_name="Старое Имя")
    r = await client.patch(
        "/api/v1/users/me", headers=auth_header(user), json={"displayName": "  Новое Имя "}
    )
    assert r.status_code == 200
    assert r.json()["displayName"] == "Новое Имя"


async def test_patch_me_rejects_blank_display_name(client, db):
    user = await make_user(db, "me@s.ru", display_name="Имя")
    r = await client.patch(
        "/api/v1/users/me", headers=auth_header(user), json={"displayName": "   "}
    )
    assert r.status_code == 422


# --- Аватар: загрузка валидных изображений ---


async def test_upload_png_avatar(client, db, tmp_storage):
    user = await make_user(db, "me@s.ru")
    png = _png_bytes()
    r = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("a.png", png, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["hasAvatar"] is True

    # hasAvatar отражается и в GET /users/me
    me = await client.get("/api/v1/users/me", headers=auth_header(user))
    assert me.json()["hasAvatar"] is True

    # GET /users/{id}/avatar возвращает те же байты с корректным content-type
    got = await client.get(f"/api/v1/users/{user.id}/avatar", headers=auth_header(user))
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert got.content == png


async def test_upload_jpeg_avatar(client, db, tmp_storage):
    user = await make_user(db, "me@s.ru")
    jpeg = _jpeg_bytes()
    r = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("a.jpg", jpeg, "image/jpeg")},
    )
    assert r.status_code == 200
    got = await client.get(f"/api/v1/users/{user.id}/avatar", headers=auth_header(user))
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/jpeg"


async def test_upload_webp_avatar(client, db, tmp_storage):
    user = await make_user(db, "me@s.ru")
    r = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("a.webp", _webp_bytes(), "image/webp")},
    )
    assert r.status_code == 200
    got = await client.get(f"/api/v1/users/{user.id}/avatar", headers=auth_header(user))
    assert got.headers["content-type"] == "image/webp"


# --- Аватар: отклонение не-изображений и превышения размера ---


async def test_reject_text_file_named_png(client, db, tmp_storage):
    """Текстовый файл с именем .png и заголовком image/png отклоняется (magic bytes)."""
    user = await make_user(db, "me@s.ru")
    r = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("evil.png", b"this is definitely not a png", "image/png")},
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    # Аватар не появился
    me = await client.get("/api/v1/users/me", headers=auth_header(user))
    assert me.json()["hasAvatar"] is False


async def test_reject_oversize_avatar(client, db, tmp_storage):
    """Файл больше max_avatar_mb отклоняется (413), даже с валидной PNG-сигнатурой."""
    from app.core.config import settings

    user = await make_user(db, "me@s.ru")
    oversize = b"\x89PNG\r\n\x1a\n" + b"\x00" * (settings.max_avatar_mb * 1024 * 1024 + 1024)
    r = await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("big.png", oversize, "image/png")},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "AVATAR_TOO_LARGE"


# --- Удаление аватара ---


async def test_delete_avatar_then_get_404(client, db, tmp_storage):
    user = await make_user(db, "me@s.ru")
    await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("a.png", _png_bytes(), "image/png")},
    )
    r = await client.delete("/api/v1/users/me/avatar", headers=auth_header(user))
    assert r.status_code == 200
    assert r.json()["hasAvatar"] is False
    got = await client.get(f"/api/v1/users/{user.id}/avatar", headers=auth_header(user))
    assert got.status_code == 404
    assert got.json()["error"]["code"] == "AVATAR_NOT_FOUND"


async def test_replace_avatar_serves_latest(client, db, tmp_storage):
    user = await make_user(db, "me@s.ru")
    await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("a.png", _png_bytes(), "image/png")},
    )
    await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(user),
        files={"file": ("a.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    got = await client.get(f"/api/v1/users/{user.id}/avatar", headers=auth_header(user))
    assert got.headers["content-type"] == "image/jpeg"  # последний победил


# --- Раздача чужого аватара требует аутентификации ---


async def test_get_other_user_avatar_requires_auth(client, db, tmp_storage):
    owner = await make_user(db, "owner@s.ru")
    await client.put(
        "/api/v1/users/me/avatar",
        headers=auth_header(owner),
        files={"file": ("a.png", _png_bytes(), "image/png")},
    )
    # Без токена — 401
    assert (await client.get(f"/api/v1/users/{owner.id}/avatar")).status_code == 401
    # Любой другой аутентифицированный пользователь — видит аватар (нужно для чата)
    other = await make_user(db, "other@s.ru")
    ok = await client.get(f"/api/v1/users/{owner.id}/avatar", headers=auth_header(other))
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "image/png"


async def test_get_avatar_404_when_none(client, db):
    user = await make_user(db, "me@s.ru")
    r = await client.get(f"/api/v1/users/{user.id}/avatar", headers=auth_header(user))
    assert r.status_code == 404
