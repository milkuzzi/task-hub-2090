"""Асинхронный движок и фабрика сессий SQLAlchemy 2.x.

`get_db` — FastAPI-зависимость, выдающая `AsyncSession` на запрос. В тестах она
переопределяется на сессию во вложенной транзакции (savepoint-rollback, §13.7.2).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    # Явные лимиты пула под скромный VPS (db: max_connections=50). Backend и
    # worker делят лимит, поэтому держим пул небольшим и с переработкой соединений.
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=1800,
    future=True,
)

SessionFactory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
