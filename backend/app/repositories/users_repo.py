"""Доступ к учётным записям (§13.3.3)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def get_active_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(
        select(User).where(User.email == email, User.is_deleted.is_(False))
    )
    return res.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_active_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    res = await db.execute(
        select(User).where(User.id == user_id, User.is_deleted.is_(False))
    )
    return res.scalar_one_or_none()


async def get_active_by_emails(db: AsyncSession, emails: Sequence[str]) -> dict[str, User]:
    """Активные пользователи по списку e-mail одним запросом (батч против N+1)."""
    if not emails:
        return {}
    res = await db.execute(
        select(User).where(User.email.in_(list(emails)), User.is_deleted.is_(False))
    )
    return {u.email: u for u in res.scalars().all()}


async def get_active_by_ids(db: AsyncSession, ids: Sequence[uuid.UUID]) -> list[User]:
    if not ids:
        return []
    res = await db.execute(
        select(User).where(User.id.in_(list(ids)), User.is_deleted.is_(False))
    )
    return list(res.scalars().all())


async def list_active(db: AsyncSession, query: str | None = None) -> list[User]:
    """Активные пользователи для выбора исполнителя/наблюдателей (§4)."""
    stmt = select(User).where(User.is_deleted.is_(False))
    if query:
        like = f"%{query}%"
        stmt = stmt.where(User.display_name.ilike(like) | User.email.ilike(like))
    stmt = stmt.order_by(User.display_name.asc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def is_admin(db: AsyncSession, user_id: uuid.UUID) -> bool:
    res = await db.execute(
        select(User.is_admin).where(User.id == user_id, User.is_deleted.is_(False))
    )
    row = res.scalar_one_or_none()
    return bool(row)


async def create(
    db: AsyncSession,
    *,
    email: str,
    password_hash: str,
    display_name: str,
    is_admin: bool = False,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    return user
