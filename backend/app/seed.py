"""Идемпотентный сид: первичный администратор + начальный реестр (§13.7.6).

Запуск: `python -m app.seed`. Повторный запуск не плодит дублей.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionFactory
from app.repositories import registry_repo, users_repo

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("seed")


async def seed() -> None:
    async with SessionFactory() as db:
        # 1. Первичный администратор
        if settings.admin_email:
            email = settings.admin_email
            if not await registry_repo.is_listed(db, email):
                await registry_repo.create(
                    db, email=email, full_name="Администратор", max_user_id=None, is_admin=True
                )
                log.info("реестр: добавлен администратор %s", email)
            user = await users_repo.get_by_email(db, email)
            if user is None and settings.admin_password:
                await users_repo.create(
                    db,
                    email=email,
                    password_hash=hash_password(settings.admin_password),
                    display_name="Администратор",
                    is_admin=True,
                )
                log.info("создана учётная запись администратора %s", email)
            await db.commit()
        else:
            log.warning("ADMIN_EMAIL не задан — администратор не создан")

        # 2. Начальный реестр из файла
        if settings.seed_registry_file:
            path = Path(settings.seed_registry_file)
            if path.exists():
                added = 0
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    entry_email = parts[0]
                    full_name = parts[1] if len(parts) > 1 and parts[1] else None
                    max_ref = parts[2] if len(parts) > 2 and parts[2] else None
                    if entry_email and not await registry_repo.is_listed(db, entry_email):
                        await registry_repo.create(
                            db,
                            email=entry_email,
                            full_name=full_name,
                            max_user_id=max_ref,
                            is_admin=False,
                        )
                        added += 1
                await db.commit()
                log.info("реестр: добавлено записей из файла: %s", added)
            else:
                log.warning("SEED_REGISTRY_FILE указан, но файл не найден: %s", path)


if __name__ == "__main__":
    asyncio.run(seed())
