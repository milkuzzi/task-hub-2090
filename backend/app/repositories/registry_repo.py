"""Доступ к реестру e-mail (белый список) (§13.2, §13.3.3)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmailRegistry


async def is_listed(db: AsyncSession, email: str) -> bool:
    res = await db.execute(select(EmailRegistry.id).where(EmailRegistry.email == email))
    return res.first() is not None


async def get_by_email(db: AsyncSession, email: str) -> EmailRegistry | None:
    res = await db.execute(select(EmailRegistry).where(EmailRegistry.email == email))
    return res.scalar_one_or_none()


async def get_by_id(db: AsyncSession, entry_id: uuid.UUID) -> EmailRegistry | None:
    return await db.get(EmailRegistry, entry_id)


async def list_entries(
    db: AsyncSession, *, query: str | None, page: int, page_size: int
) -> tuple[list[EmailRegistry], int]:
    stmt = select(EmailRegistry)
    count_stmt = select(func.count()).select_from(EmailRegistry)
    if query:
        like = f"%{query}%"
        cond = or_(EmailRegistry.email.ilike(like), EmailRegistry.full_name.ilike(like))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(EmailRegistry.created_at.desc()).offset((page - 1) * page_size).limit(
        page_size
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, total


async def create(
    db: AsyncSession,
    *,
    email: str,
    full_name: str | None,
    max_user_id: str | None,
    is_admin: bool,
) -> EmailRegistry:
    entry = EmailRegistry(
        email=email, full_name=full_name, max_user_id=max_user_id, is_admin=is_admin
    )
    db.add(entry)
    await db.flush()
    return entry


async def delete(db: AsyncSession, entry: EmailRegistry) -> None:
    await db.delete(entry)
    await db.flush()
