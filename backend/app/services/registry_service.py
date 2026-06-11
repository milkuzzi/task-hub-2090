"""Ведение реестра e-mail и удаление пользователя с архивом (§13.2.9, §13.5.4)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core import errors
from app.core.clock import now
from app.repositories import registry_repo, tasks_repo, tokens_repo, users_repo
from app.schemas.admin import (
    RegistryCreateIn,
    RegistryItemOut,
    RegistryUpdateIn,
    UserDeleteResult,
)
from app.storage.base import get_storage

TOMBSTONE_NAME = "Пользователь удалён"


async def _to_item(db: AsyncSession, entry) -> RegistryItemOut:
    user = await users_repo.get_active_by_email(db, entry.email)
    return RegistryItemOut(
        id=entry.id,
        email=entry.email,
        full_name=entry.full_name,
        max_contact=entry.max_user_id,
        is_admin=entry.is_admin,
        registered=user is not None,
        user_id=user.id if user else None,
    )


async def list_registry(
    db: AsyncSession, *, query: str | None, page: int, page_size: int
) -> tuple[list[RegistryItemOut], int]:
    rows, total = await registry_repo.list_entries(
        db, query=query, page=page, page_size=page_size
    )
    items = [await _to_item(db, r) for r in rows]
    return items, total


async def create_entry(db: AsyncSession, data: RegistryCreateIn) -> RegistryItemOut:
    if await registry_repo.is_listed(db, data.email):
        raise errors.email_already_registered()
    entry = await registry_repo.create(
        db,
        email=data.email,
        full_name=data.full_name,
        max_user_id=data.max_contact,
        is_admin=data.is_admin,
    )
    # синхронизируем флаг администратора с уже существующей учёткой (если есть)
    user = await users_repo.get_active_by_email(db, data.email)
    if user is not None:
        user.is_admin = data.is_admin
    await db.commit()
    return await _to_item(db, entry)


async def update_entry(
    db: AsyncSession, entry_id: uuid.UUID, data: RegistryUpdateIn
) -> RegistryItemOut:
    entry = await registry_repo.get_by_id(db, entry_id)
    if entry is None:
        raise errors.user_not_found()
    if data.email is not None and data.email != entry.email:
        if await registry_repo.is_listed(db, data.email):
            raise errors.email_already_registered()
        entry.email = data.email
    if data.full_name is not None:
        entry.full_name = data.full_name
    if data.max_contact is not None:
        entry.max_user_id = data.max_contact
    if data.is_admin is not None:
        entry.is_admin = data.is_admin
        user = await users_repo.get_active_by_email(db, entry.email)
        if user is not None:
            user.is_admin = data.is_admin
    await db.commit()
    return await _to_item(db, entry)


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID) -> None:
    """Мягко: убрать e-mail из реестра → вход блокируется (архив не трогаем) (§13.5.4)."""
    entry = await registry_repo.get_by_id(db, entry_id)
    if entry is None:
        raise errors.user_not_found()
    await registry_repo.delete(db, entry)
    await db.commit()


async def delete_user_and_archive(
    db: AsyncSession, user_id: uuid.UUID, actor: CurrentUser
) -> UserDeleteResult:
    """Жёстко: удалить пользователя и весь его архив (§3 п.10, §13.2.9)."""
    user = await users_repo.get_by_id(db, user_id)
    if user is None or user.is_deleted:
        raise errors.user_not_found()

    original_email = user.email
    file_paths = await tasks_repo.collect_author_file_paths(db, user_id)
    tasks_count = await tasks_repo.delete_authored_tasks(db, user_id)
    flagged = await tasks_repo.flag_foreign_for_reassignment(db, user_id)
    await tasks_repo.anonymize_observer(db, user_id)

    # tombstone учётки: вход невозможен, личность обезличена, e-mail освобождён
    user.is_deleted = True
    user.deleted_at = now()
    user.display_name = TOMBSTONE_NAME
    user.email = f"deleted+{user_id}@removed.local"
    user.password_hash = ""
    user.is_admin = False
    await tokens_repo.revoke_all_refresh(db, user_id)

    entry = await registry_repo.get_by_email(db, original_email)
    if entry is not None:
        await registry_repo.delete(db, entry)

    await db.commit()

    # удаление файлов — вне транзакции БД
    get_storage().delete_many(file_paths)

    return UserDeleteResult(
        deleted_tasks_as_author=tasks_count,
        deleted_attachments=len(file_paths),
        flagged_for_reassignment=flagged,
    )
