"""DTO профиля пользователя (§8, task-collaboration).

Профиль редактируется самим пользователем: отображаемое имя и контакт MAX
(`email_registry.max_user_id`). Аватар управляется отдельными эндпойнтами
(`PUT/DELETE /users/me/avatar`); здесь отдаётся лишь признак его наличия.
"""

from __future__ import annotations

import uuid

from app.schemas.common import CamelModel


class ProfileOut(CamelModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool
    max_contact: str | None = None
    has_avatar: bool = False


class ProfileUpdateIn(CamelModel):
    # Оба поля опциональны: переданное поле редактируется, отсутствующее — нет.
    # Пустая строка в maxContact очищает контакт (см. profile_service).
    max_contact: str | None = None
    display_name: str | None = None
