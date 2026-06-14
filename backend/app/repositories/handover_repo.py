"""Доступ к отложенной передаче администрирования (Требование 2).

Исходящий администратор ПОНИЖАЕТСЯ до обычного пользователя (его данные
сохраняются), а не удаляется. Понижение и повышение входящего происходят
атомарно вместе с удалением строки handover.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PendingAdminHandover
from app.repositories import registry_repo, users_repo


async def create(
    db: AsyncSession, *, incoming_id: uuid.UUID, outgoing_id: uuid.UUID
) -> None:
    """Зафиксировать намерение передать администрирование (идемпотентно)."""
    stmt = (
        pg_insert(PendingAdminHandover)
        .values(incoming_user_id=incoming_id, outgoing_user_id=outgoing_id)
        .on_conflict_do_nothing(index_elements=["incoming_user_id"])
    )
    await db.execute(stmt)
    await db.flush()


async def complete_for(db: AsyncSession, incoming_id: uuid.UUID) -> uuid.UUID | None:
    """Завершить передачу для активировавшегося входящего администратора.

    Понижает исходящего (is_admin=false и в users, и в реестре — данные не
    трогаем), повышает входящего (is_admin=true там же) и удаляет строку
    handover. Возвращает id исходящего, если передача была завершена.
    """
    res = await db.execute(
        select(PendingAdminHandover).where(
            PendingAdminHandover.incoming_user_id == incoming_id
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        return None

    outgoing_id = row.outgoing_user_id

    # Понижаем исходящего администратора (данные сохраняются).
    outgoing = await users_repo.get_by_id(db, outgoing_id)
    if outgoing is not None:
        outgoing.is_admin = False
        out_entry = await registry_repo.get_by_email(db, outgoing.email)
        if out_entry is not None:
            out_entry.is_admin = False

    # Повышаем входящего администратора.
    incoming = await users_repo.get_by_id(db, incoming_id)
    if incoming is not None:
        incoming.is_admin = True
        in_entry = await registry_repo.get_by_email(db, incoming.email)
        if in_entry is not None:
            in_entry.is_admin = True

    await db.delete(row)
    await db.flush()
    return outgoing_id
