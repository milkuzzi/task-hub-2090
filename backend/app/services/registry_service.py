"""Ведение реестра e-mail и удаление пользователя с архивом (§13.2.9, §13.5.4)."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core import errors
from app.core.clock import now
from app.core.security import generate_opaque_token, hash_token
from app.repositories import handover_repo, registry_repo, tasks_repo, tokens_repo, users_repo
from app.schemas.admin import (
    RegistryCreateIn,
    RegistryItemOut,
    RegistryUpdateIn,
    TransferAdminOut,
    UserDeleteResult,
)
from app.services import auth_service
from app.storage.base import get_storage

TOMBSTONE_NAME = "Пользователь удалён"

# Advisory-lock для сериализации передачи администрирования (любой стабильный bigint).
_TRANSFER_ADMIN_LOCK_KEY = 48230002


async def _to_item(db: AsyncSession, entry, *, user=None) -> RegistryItemOut:
    # user можно передать заранее (батч-выборка), иначе берём точечно по e-mail.
    if user is None:
        user = await users_repo.get_active_by_email(db, entry.email)
    # «Зарегистрирован» = учётка активирована (пароль задан), а не просто заведена.
    activated = user is not None and user.password_hash is not None
    return RegistryItemOut(
        id=entry.id,
        email=entry.email,
        full_name=entry.full_name,
        max_contact=entry.max_user_id,
        is_admin=entry.is_admin,
        registered=activated,
        user_id=user.id if user else None,
    )


async def list_registry(
    db: AsyncSession, *, query: str | None, page: int, page_size: int
) -> tuple[list[RegistryItemOut], int]:
    rows, total = await registry_repo.list_entries(
        db, query=query, page=page, page_size=page_size
    )
    # Один батч-запрос вместо N точечных get_active_by_email (анти-N+1).
    users_by_email = await users_repo.get_active_by_emails(db, [r.email for r in rows])
    items = [await _to_item(db, r, user=users_by_email.get(r.email)) for r in rows]
    return items, total


async def create_entry(db: AsyncSession, data: RegistryCreateIn) -> RegistryItemOut:
    if await registry_repo.is_listed(db, data.email):
        raise errors.email_already_registered()
    # Админ через реестр НЕ выдаётся — только консоль и передача администрирования.
    # MAX (max_user_id) администратор не задаёт — поле станет пользовательским позже.
    entry = await registry_repo.create(
        db,
        email=data.email,
        full_name=data.full_name,
        max_user_id=None,
        is_admin=False,
    )

    # Приглашение по e-mail (Требование 4): создаём НЕактивную учётку и высылаем
    # ссылку «задайте пароль». Если живая учётка уже есть, но не активирована —
    # переотправляем приглашение. Если активна — просто запись в реестре.
    user = await users_repo.get_active_by_email(db, data.email)
    raw: str | None = None
    if user is None:
        display_name = data.full_name if data.full_name else data.email.split("@")[0]
        user = await users_repo.create(
            db,
            email=data.email,
            password_hash=None,
            display_name=display_name,
            is_admin=False,
        )
        raw = generate_opaque_token()
        await tokens_repo.create_reset(db, user_id=user.id, token_hash=hash_token(raw))
    elif user.password_hash is None:
        raw = generate_opaque_token()
        await tokens_repo.create_reset(db, user_id=user.id, token_hash=hash_token(raw))

    await db.commit()
    if raw is not None:
        await auth_service._send_invitation_email(data.email, raw)  # письмо best-effort
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
    # MAX (max_user_id) администратор не меняет — поле станет пользовательским позже.
    # is_admin через реестр не меняется (только консоль и передача администрирования).
    await db.commit()
    return await _to_item(db, entry)


async def transfer_admin(
    db: AsyncSession, actor: CurrentUser, email: str
) -> TransferAdminOut:
    """Передать администрирование другому лицу; исходящий админ ПОНИЖАЕТСЯ (Требование 2).

    Проверка единственного админа, повышение входящего и регистрация handover
    выполняются под advisory-lock, чтобы две параллельные передачи не прошли обе.
    """
    if email == actor.email:
        raise errors.self_transfer()

    # Сериализуем одновременные передачи администрирования в рамках транзакции:
    # второй параллельный запрос ждёт здесь, пока первый не закоммитит (и увидит
    # уже двух админов → not_sole_admin).
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:k)"), {"k": _TRANSFER_ADMIN_LOCK_KEY}
    )

    if await users_repo.count_admins(db) != 1:
        raise errors.not_sole_admin()

    user, has_password = await auth_service.promote_or_create_admin(db, email)
    await handover_repo.create(db, incoming_id=user.id, outgoing_id=actor.id)

    if has_password:
        # Входящий уже может войти — завершаем передачу немедленно.
        await handover_repo.complete_for(db, user.id)
        await db.commit()
        return TransferAdminOut(completed=True, email=user.email)

    # Отложенная активация: промоут+handover закоммичены, письмо НЕ откатывает их.
    raw = generate_opaque_token()
    await tokens_repo.create_reset(db, user_id=user.id, token_hash=hash_token(raw))
    await db.commit()
    email_sent = await auth_service._send_invitation_email(user.email, raw)
    return TransferAdminOut(completed=False, email=user.email, email_sent=email_sent)


async def delete_entry(db: AsyncSession, entry_id: uuid.UUID, actor: CurrentUser) -> None:
    """Мягко: убрать e-mail из реестра → вход блокируется (архив не трогаем) (§13.5.4)."""
    entry = await registry_repo.get_by_id(db, entry_id)
    if entry is None:
        raise errors.user_not_found()
    # Нельзя выбить из реестра самого себя (само-блокировка).
    if entry.email == actor.email:
        raise errors.self_deletion()
    # Нельзя убрать запись администратора — сначала передать администрирование.
    user = await users_repo.get_active_by_email(db, entry.email)
    if entry.is_admin or (user is not None and user.is_admin):
        raise errors.admin_delete_forbidden()
    await registry_repo.delete(db, entry)
    await db.commit()


async def delete_user_and_archive(
    db: AsyncSession, user_id: uuid.UUID, actor: CurrentUser
) -> UserDeleteResult:
    """Жёстко: удалить пользователя и весь его архив (§3 п.10, §13.2.9)."""
    # Нельзя удалить самого себя.
    if user_id == actor.id:
        raise errors.self_deletion()

    user = await users_repo.get_by_id(db, user_id)
    if user is None or user.is_deleted:
        raise errors.user_not_found()
    # Администратора удалить нельзя — сначала передать администрирование.
    if user.is_admin:
        raise errors.admin_delete_forbidden()

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
