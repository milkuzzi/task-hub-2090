"""DTO администрирования реестра (§13.5.4)."""

from __future__ import annotations

import uuid

from pydantic import EmailStr

from app.schemas.common import CamelModel


class RegistryItemOut(CamelModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    max_contact: str | None = None
    is_admin: bool = False
    registered: bool = False  # владелец уже завёл пароль
    user_id: uuid.UUID | None = None


class RegistryListResponse(CamelModel):
    items: list[RegistryItemOut]
    total: int


class RegistryCreateIn(CamelModel):
    email: EmailStr
    full_name: str | None = None
    max_contact: str | None = None
    is_admin: bool = False


class RegistryUpdateIn(CamelModel):
    email: EmailStr | None = None
    full_name: str | None = None
    max_contact: str | None = None
    is_admin: bool | None = None


class UserDeleteResult(CamelModel):
    ok: bool = True
    deleted_tasks_as_author: int = 0
    deleted_attachments: int = 0
    flagged_for_reassignment: int = 0
