"""Профиль пользователя: чтение/редактирование своих данных и аватар (§8).

Самостоятельное редактирование (Req 8.1): отображаемое имя и контакт MAX
(хранится в реестре `email_registry.max_user_id`, резолвится по e-mail). Аватар
(Req 7): загрузка/замена/удаление с проверкой типа по СОДЕРЖИМОМУ (magic bytes),
а не только по расширению/заголовку, и ограничением размера; хранение — в общем
сторадже вложений (UUID-ключ), раздача — отдельным эндпойнтом для аутентифицированных.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core import errors
from app.core.config import settings
from app.models import User
from app.repositories import registry_repo, users_repo
from app.schemas.profile import ProfileOut, ProfileUpdateIn
from app.services import attachment_service
from app.storage.base import get_storage

# Разумный предел длины человекочитаемых полей профиля.
_MAX_CONTACT_LEN = 100
_MAX_DISPLAY_NAME_LEN = 120

# Допустимые типы аватара. Ключ — content-type, значение — детектор по magic bytes.
PNG_CONTENT_TYPE = "image/png"
JPEG_CONTENT_TYPE = "image/jpeg"
WEBP_CONTENT_TYPE = "image/webp"

ALLOWED_AVATAR_CONTENT_TYPES = (PNG_CONTENT_TYPE, JPEG_CONTENT_TYPE, WEBP_CONTENT_TYPE)


@dataclass
class AvatarData:
    """Готовые байты аватара для раздачи (с уже определённым content-type)."""

    content_type: str
    data: bytes


def detect_image_type(data: bytes) -> str | None:
    """Определяет тип изображения по сигнатуре (magic bytes), а не по расширению.

    Возвращает content-type ('image/png' | 'image/jpeg' | 'image/webp') либо None,
    если содержимое не похоже ни на один из разрешённых форматов. Так подделанный
    по имени/заголовку файл (например, .png с текстом внутри) будет отклонён.
    """
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG_CONTENT_TYPE
    # JPEG: FF D8 FF
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG_CONTENT_TYPE
    # WebP: 'RIFF' .... 'WEBP' (RIFF-контейнер с формой WEBP)
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP_CONTENT_TYPE
    return None


async def _max_contact_of(db: AsyncSession, email: str) -> str | None:
    entry = await registry_repo.get_by_email(db, email)
    return entry.max_user_id if entry else None


def _profile_out(user: User, *, max_contact: str | None) -> ProfileOut:
    return ProfileOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_admin=user.is_admin,
        max_contact=max_contact,
        has_avatar=user.avatar_path is not None,
    )


async def get_my_profile(db: AsyncSession, current: CurrentUser) -> ProfileOut:
    user = await users_repo.get_active_by_id(db, current.id)
    if user is None:
        raise errors.user_not_found()
    return _profile_out(user, max_contact=await _max_contact_of(db, user.email))


def _validate_max_contact(raw: str) -> str | None:
    """Нормализует и валидирует контакт MAX. Пустая строка → None (очистка)."""
    value = raw.strip()
    if not value:
        return None
    if len(value) > _MAX_CONTACT_LEN:
        raise errors.validation_error(
            [
                {
                    "field": "maxContact",
                    "message": f"Контакт MAX не длиннее {_MAX_CONTACT_LEN} символов.",
                }
            ]
        )
    # Базовая защита: без управляющих символов/переводов строк.
    if any(ord(ch) < 32 for ch in value):
        raise errors.validation_error(
            [{"field": "maxContact", "message": "Контакт MAX содержит недопустимые символы."}]
        )
    return value


def _validate_display_name(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise errors.validation_error(
            [{"field": "displayName", "message": "Имя не может быть пустым."}]
        )
    if len(value) > _MAX_DISPLAY_NAME_LEN:
        raise errors.validation_error(
            [
                {
                    "field": "displayName",
                    "message": f"Имя не длиннее {_MAX_DISPLAY_NAME_LEN} символов.",
                }
            ]
        )
    return value


async def update_my_profile(
    db: AsyncSession, current: CurrentUser, data: ProfileUpdateIn
) -> ProfileOut:
    """Самостоятельное редактирование профиля (Req 8.1, 7-смежно).

    `maxContact`: переданная строка валидируется/нормализуется; пустая строка
    очищает контакт. `displayName`: непустое имя в пределах лимита. Отсутствующее
    в запросе поле не трогаем (различаем по `model_fields_set`).
    """
    user = await users_repo.get_active_by_id(db, current.id)
    if user is None:
        raise errors.user_not_found()

    fields = data.model_fields_set

    if "display_name" in fields and data.display_name is not None:
        user.display_name = _validate_display_name(data.display_name)

    if "max_contact" in fields:
        new_max = _validate_max_contact(data.max_contact or "")
        entry = await registry_repo.get_by_email(db, user.email)
        if entry is None:
            # Пользователь без записи в реестре доступа не имеет — защитный случай.
            raise errors.user_not_found()
        entry.max_user_id = new_max

    await db.commit()
    await db.refresh(user)
    return _profile_out(user, max_contact=await _max_contact_of(db, user.email))


async def set_avatar(db: AsyncSession, current: CurrentUser, upload: UploadFile) -> ProfileOut:
    """Загрузка/замена аватара (Req 7.1, 7.2, 7.5).

    Размер ограничен `max_avatar_mb` (переиспользуем потоковое bounded-чтение).
    Тип проверяется по magic bytes содержимого — заголовок/имя не доверяются.
    При замене прежний файл удаляется из стораджа.
    """
    user = await users_repo.get_active_by_id(db, current.id)
    if user is None:
        raise errors.user_not_found()

    data = await attachment_service.read_upload_bounded(
        upload,
        max_bytes=settings.max_avatar_mb * 1024 * 1024,
        too_large=lambda: errors.avatar_too_large(settings.max_avatar_mb),
    )
    if detect_image_type(data) is None:
        raise errors.unsupported_media_type()

    storage = get_storage()
    # Сохраняем под namespace = user.id → ключ "<user_id>/<uuid>".
    stored = storage.save(user.id, data)
    previous = user.avatar_path
    user.avatar_path = stored.stored_key
    try:
        await db.commit()
    except Exception:
        storage.delete(stored.stored_key)  # компенсация: не плодим осиротевшие файлы
        raise
    await db.refresh(user)

    # Прежний файл удаляем только после успешного коммита замены.
    if previous and previous != stored.stored_key:
        storage.delete(previous)

    return _profile_out(user, max_contact=await _max_contact_of(db, user.email))


async def delete_avatar(db: AsyncSession, current: CurrentUser) -> ProfileOut:
    """Удаление аватара → возврат к заглушке-инициалам (Req 7.4)."""
    user = await users_repo.get_active_by_id(db, current.id)
    if user is None:
        raise errors.user_not_found()

    previous = user.avatar_path
    user.avatar_path = None
    await db.commit()
    await db.refresh(user)

    if previous:
        get_storage().delete(previous)

    return _profile_out(user, max_contact=await _max_contact_of(db, user.email))


async def get_avatar(db: AsyncSession, user_id: uuid.UUID) -> AvatarData:
    """Байты аватара пользователя для раздачи (любому аутентифицированному).

    Content-type определяется по содержимому (тому же magic-byte детектору), чтобы
    отдать корректный заголовок без отдельной колонки MIME. 404 — если у
    пользователя нет аватара (фронт рисует инициалы).
    """
    user = await users_repo.get_active_by_id(db, user_id)
    if user is None or not user.avatar_path:
        raise errors.avatar_not_found()
    path = get_storage().path_of(user.avatar_path)
    if not path.exists():
        raise errors.avatar_not_found()
    data = path.read_bytes()
    content_type = detect_image_type(data) or "application/octet-stream"
    return AvatarData(content_type=content_type, data=data)
