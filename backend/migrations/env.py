"""Alembic env: онлайн-миграции поверх асинхронного движка (§13.7.5).

Схема создаётся прогоном `upgrade head` (а не metadata.create_all) — чтобы в
тестах и проде была одна и та же схема, включая частичные индексы и триггеры.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Импортируем модели, чтобы наполнить Base.metadata (для autogenerate при желании).
import app.models  # noqa: F401,E402
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    # Для миграций используем тот же URL; драйвер asyncpg поддерживается через run_sync.
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(_sync_url(), pool_pre_ping=True)
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
