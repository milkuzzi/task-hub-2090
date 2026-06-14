"""Гард-команда создания первичного администратора (Требование 1).

Запуск:
    ADMIN_CREATION_TOKEN="<token>" python -m app.cli.create_admin --email admin@example.com [--force]

Безопасность (зеркалит tagcloud scripts/create-admin.ts):
  - переменная окружения ADMIN_CREATION_TOKEN обязательна и сверяется timing-safe
    (hmac.compare_digest) с настройкой ADMIN_CREATION_TOKEN сервера. Без неё доступ
    к одному лишь DATABASE_URL не позволяет «отчеканить» администратора.
  - Система рассчитана на ЕДИНСТВЕННОГО администратора: если живой админ уже есть,
    команда отказывает (используйте передачу администрирования в UI), кроме случая
    запуска с --force.

Команда повышает существующего пользователя или создаёт новую учётку с
password_hash=NULL и печатает в stdout ссылку «задайте пароль» для администратора.
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import os
import sys

from app.core.config import settings
from app.core.security import generate_opaque_token, hash_token
from app.db.session import SessionFactory
from app.repositories import tokens_repo, users_repo
from app.services import auth_service


async def _run(email: str, force: bool) -> int:
    provided = os.environ.get("ADMIN_CREATION_TOKEN")
    expected = settings.admin_creation_token
    if not provided or not expected:
        print(
            "Ошибка: ADMIN_CREATION_TOKEN не задан "
            "(нужны переменная окружения и настройка сервера).",
            file=sys.stderr,
        )
        return 1
    if not hmac.compare_digest(provided, expected):
        print("Ошибка: ADMIN_CREATION_TOKEN не совпадает с ожидаемым.", file=sys.stderr)
        return 1

    async with SessionFactory() as db:
        existing = await users_repo.count_admins(db)
        if existing > 0 and not force:
            print(
                f"Администратор уже существует ({existing}). Создание отклонено.\n"
                "Передайте администрирование через интерфейс или используйте --force.",
                file=sys.stderr,
            )
            return 1

        user, has_password = await auth_service.promote_or_create_admin(db, email)
        raw = generate_opaque_token()
        await tokens_repo.create_reset(db, user_id=user.id, token_hash=hash_token(raw))
        await db.commit()

        link = f"{settings.base_url.rstrip('/')}/reset/confirm?token={raw}"
        if has_password:
            print(f"\nПользователь {email} повышен до администратора (пароль уже задан).")
        print("\nОтправьте администратору эту ссылку, чтобы задать пароль:")
        print(f"\n  {link}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Создать/повысить первичного администратора (гард по ADMIN_CREATION_TOKEN)."
    )
    parser.add_argument("--email", required=True, help="E-mail администратора")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Создать даже если администратор уже существует",
    )
    args = parser.parse_args()
    email = args.email.strip().lower()
    sys.exit(asyncio.run(_run(email, args.force)))


if __name__ == "__main__":
    main()
