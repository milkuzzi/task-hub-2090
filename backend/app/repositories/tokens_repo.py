"""Доступ к refresh- и reset-токенам (§13.3.2, §13.3.4)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now
from app.core.config import settings
from app.models import PasswordResetToken, RefreshToken

# --- refresh ---


async def create_refresh(db: AsyncSession, *, user_id: uuid.UUID, token_hash: str) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now() + timedelta(days=settings.refresh_ttl_days),
    )
    db.add(token)
    await db.flush()
    return token


async def get_active_refresh(db: AsyncSession, token_hash: str) -> RefreshToken | None:
    res = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    obj = res.scalar_one_or_none()
    if obj is None or obj.revoked_at is not None or obj.expires_at <= now():
        return None
    return obj


async def revoke_refresh(db: AsyncSession, token: RefreshToken) -> None:
    token.revoked_at = now()
    await db.flush()


async def revoke_all_refresh(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    await db.flush()


# --- reset ---


async def create_reset(db: AsyncSession, *, user_id: uuid.UUID, token_hash: str) -> PasswordResetToken:
    token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=now() + timedelta(minutes=settings.password_reset_ttl_min),
    )
    db.add(token)
    await db.flush()
    return token


async def get_valid_reset(db: AsyncSession, token_hash: str) -> PasswordResetToken | None:
    res = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    obj = res.scalar_one_or_none()
    if obj is None or obj.used_at is not None or obj.expires_at <= now():
        return None
    return obj


async def mark_reset_used(db: AsyncSession, token: PasswordResetToken) -> None:
    token.used_at = now()
    await db.flush()
