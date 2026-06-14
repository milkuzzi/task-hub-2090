"""Тестовая инфраструктура (§13.7.2).

Тест-БД — настоящий PostgreSQL. Схема создаётся прогоном миграций (upgrade head).
Изоляция — внешняя транзакция + savepoint-сессия, откатываемая на teardown.
Время управляется через инъецируемый clock.now(); каналы — in-memory фейки.
"""

from __future__ import annotations

import os

# Должно стоять ДО импорта app.* — settings читает DATABASE_URL на импорте.
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres:test@localhost:5433/test"),
)
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("BASE_URL", "http://test")
# Rate limit глобально выключен, чтобы массовые логины в тестах не ловили 429;
# точечно включается в tests/integration/test_ratelimit.py.
os.environ.setdefault("AUTH_RATE_LIMIT_ENABLED", "false")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core import clock  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.notifications.channel import ChannelKind  # noqa: E402
from app.notifications.registry import set_channels  # noqa: E402
from tests.fakes import FakeChannel  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrate():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def db():
    # Свой движок на цикл теста (NullPool) — никакого переиспользования соединений
    # между event loop'ами разных тестов.
    eng = create_async_engine(settings.database_url, poolclass=NullPool)
    conn = await eng.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        await session.close()
        if trans.is_active:
            await trans.rollback()
        await conn.close()
        await eng.dispose()


@pytest_asyncio.fixture
async def client(db):
    async def _override():
        try:
            yield db
        except AppError:
            raise  # контролируемая доменная ошибка — сессия чистая, не истекаем объекты
        except Exception:
            await db.rollback()
            raise

    app.dependency_overrides[get_db] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def fake_channels():
    """In-memory каналы; возвращает (email, max). MAX по умолчанию доступен."""
    email = FakeChannel(ChannelKind.EMAIL)
    mx = FakeChannel(ChannelKind.MAX)
    set_channels({ChannelKind.EMAIL: email, ChannelKind.MAX: mx})
    yield email, mx


@pytest.fixture(autouse=True)
def _reset_clock():
    yield
    clock.set_now_override(None)


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine():
    """Сбрасываем пул глобального движка между тестами.

    Фоновые задачи (например, notify_assignment) используют глобальный
    `SessionFactory`, минуя override `get_db`. У pytest-asyncio каждый тест
    выполняется в собственном event loop, поэтому соединение из пула,
    созданное в прошлом тесте, при повторном использовании даёт ошибку
    «attached to a different loop». Диспоуз после каждого теста гарантирует
    свежие соединения в текущем loop.
    """
    yield
    from app.db import session as _session

    await _session.engine.dispose()
