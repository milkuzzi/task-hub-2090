"""Безопасность: argon2id-хэширование паролей, JWT access-токены, непрозрачные
refresh/reset-токены (§13.3.2, §13.7.4).

Пароли хэшируются argon2id напрямую через argon2-cffi (без passlib — устойчивее
на Python 3.12). refresh/reset-токены хранятся в БД ТОЛЬКО как sha256-хэш.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.clock import now
from app.core.config import settings

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_access_token(*, user_id: uuid.UUID, email: str, is_admin: bool) -> str:
    issued = now()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(minutes=settings.jwt_access_ttl_min)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Бросает jwt.PyJWTError при невалидной подписи/истечении."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_opaque_token() -> str:
    """Случайный непрозрачный токен (refresh / сброс пароля)."""
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
