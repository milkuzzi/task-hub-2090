"""Интеграция: rate limit на auth-эндпоинтах — после превышения лимита 429 RATE_LIMITED."""

from __future__ import annotations

import pytest

from app.core import ratelimit
from app.core.config import settings


@pytest.fixture(autouse=True)
def _enable_rate_limit():
    """Включаем лимитер (глобально выключен в conftest) и чистим счётчики."""
    ratelimit.reset()
    settings.auth_rate_limit_enabled = True
    yield
    settings.auth_rate_limit_enabled = False
    ratelimit.reset()


async def test_login_rate_limited_after_10_attempts(client):
    payload = {"email": "bruteforce@school.ru", "password": "wrong-password"}
    for _ in range(10):
        r = await client.post("/api/v1/auth/login", json=payload)
        assert r.status_code == 401  # неверные креды, но ещё не лимит
    r = await client.post("/api/v1/auth/login", json=payload)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


async def test_reset_request_rate_limited_after_5_attempts(client):
    payload = {"email": "someone@school.ru"}
    for _ in range(5):
        r = await client.post("/api/v1/auth/password-reset/request", json=payload)
        assert r.status_code == 200  # всегда нейтральный «ок»
    r = await client.post("/api/v1/auth/password-reset/request", json=payload)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


async def test_scopes_are_independent(client):
    """Исчерпание лимита сброса пароля не блокирует вход."""
    for _ in range(6):
        await client.post("/api/v1/auth/password-reset/request", json={"email": "a@b.ru"})
    r = await client.post(
        "/api/v1/auth/login", json={"email": "a@b.ru", "password": "wrong-password"}
    )
    assert r.status_code == 401  # не 429: другой scope
