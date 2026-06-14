"""DTO аутентификации и сброса пароля (§13.5.4)."""

from __future__ import annotations

import uuid

from pydantic import EmailStr, Field

from app.schemas.common import CamelModel


class LoginIn(CamelModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(CamelModel):
    id: uuid.UUID
    email: str
    is_admin: bool
    display_name: str


class TokenOut(CamelModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ResetRequestIn(CamelModel):
    email: EmailStr


class ResetConfirmIn(CamelModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=200)
