"""Сценарии аутентификации, сессий и сброса пароля (§13.3.2–13.3.4)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import User
from app.notifications.channel import ChannelKind, Message, Recipient
from app.notifications.registry import get_channel
from app.repositories import registry_repo, tokens_repo, users_repo


async def _issue_tokens(db: AsyncSession, user: User) -> tuple[str, str]:
    access = create_access_token(user_id=user.id, email=user.email, is_admin=user.is_admin)
    raw = generate_opaque_token()
    await tokens_repo.create_refresh(db, user_id=user.id, token_hash=hash_token(raw))
    return access, raw


async def register(db: AsyncSession, *, email: str, password: str) -> tuple[User, str, str]:
    if not await registry_repo.is_listed(db, email):
        raise errors.email_not_in_registry()  # дословная фраза отказа (§3 п.3)
    if await users_repo.get_by_email(db, email) is not None:
        raise errors.email_already_registered()
    entry = await registry_repo.get_by_email(db, email)
    display_name = entry.full_name if entry and entry.full_name else email.split("@")[0]
    is_admin = bool(entry and entry.is_admin)
    user = await users_repo.create(
        db,
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        is_admin=is_admin,
    )
    access, raw = await _issue_tokens(db, user)
    await db.commit()
    return user, access, raw


async def login(db: AsyncSession, *, email: str, password: str) -> tuple[User, str, str]:
    user = await users_repo.get_active_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise errors.unauthenticated()
    if not await registry_repo.is_listed(db, email):
        raise errors.registry_access_revoked()
    access, raw = await _issue_tokens(db, user)
    await db.commit()
    return user, access, raw


async def refresh(db: AsyncSession, *, raw_refresh: str | None) -> tuple[User, str, str]:
    if not raw_refresh:
        raise errors.unauthenticated()
    token = await tokens_repo.get_active_refresh(db, hash_token(raw_refresh))
    if token is None:
        raise errors.unauthenticated()
    user = await users_repo.get_active_by_id(db, token.user_id)
    if user is None or not await registry_repo.is_listed(db, user.email):
        raise errors.registry_access_revoked()
    await tokens_repo.revoke_refresh(db, token)  # ротация: старый токен инвалидируется
    access, new_raw = await _issue_tokens(db, user)
    await db.commit()
    return user, access, new_raw


async def logout(db: AsyncSession, *, raw_refresh: str | None) -> None:
    if raw_refresh:
        token = await tokens_repo.get_active_refresh(db, hash_token(raw_refresh))
        if token is not None:
            await tokens_repo.revoke_refresh(db, token)
    await db.commit()


async def request_password_reset(db: AsyncSession, *, email: str) -> None:
    """Всегда «ок» снаружи — не раскрываем наличие e-mail (§13.5.4)."""
    user = await users_repo.get_active_by_email(db, email)
    if user is not None and await registry_repo.is_listed(db, email):
        raw = generate_opaque_token()
        await tokens_repo.create_reset(db, user_id=user.id, token_hash=hash_token(raw))
        await db.commit()
        await _send_reset_email(user.email, raw)
    else:
        await db.commit()


async def _send_reset_email(email: str, raw_token: str) -> None:
    link = f"{settings.base_url.rstrip('/')}/reset/confirm?token={raw_token}"
    body = (
        "Вы запросили восстановление пароля в сервисе поручений школы № 2090.\n"
        f"Перейдите по ссылке, чтобы задать новый пароль (действует ограниченное время):\n{link}\n\n"
        "Если вы не запрашивали сброс — просто игнорируйте это письмо."
    )
    msg = Message(subject="Восстановление пароля — школа № 2090", body_text=body)
    try:
        await get_channel(ChannelKind.EMAIL).send(Recipient(user_id="", email=email), msg)
    except Exception:  # noqa: BLE001 — письмо best-effort на этом шаге, ответ всегда нейтральный
        pass


async def confirm_password_reset(db: AsyncSession, *, token: str, new_password: str) -> None:
    reset = await tokens_repo.get_valid_reset(db, hash_token(token))
    if reset is None:
        raise errors.bad_request("Токен сброса недействителен или истёк.")
    user = await users_repo.get_active_by_id(db, reset.user_id)
    if user is None or not await registry_repo.is_listed(db, user.email):
        raise errors.bad_request("Токен сброса недействителен или истёк.")
    user.password_hash = hash_password(new_password)
    await tokens_repo.mark_reset_used(db, reset)
    await tokens_repo.revoke_all_refresh(db, user.id)  # вынуждаем перелогиниться
    await db.commit()
