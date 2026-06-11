"""Rate limit для чувствительных эндпоинтов (вход, сброс пароля).

Скользящее окно по паре (scope, IP клиента), хранение в памяти процесса.
Для одного uvicorn-процесса этого достаточно; при нескольких воркерах лимит
действует на каждый процесс отдельно (для масштаба одной организации приемлемо).
uvicorn запущен с --proxy-headers, поэтому request.client.host за Caddy —
реальный IP клиента.

Отключение (для автотестов): AUTH_RATE_LIMIT_ENABLED=false.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core import errors
from app.core.config import settings

_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)

# Защита от разрастания памяти: при превышении — чистим устаревшие ключи.
_MAX_KEYS = 10_000


def reset() -> None:
    """Сброс всех счётчиков (используется в тестах)."""
    _buckets.clear()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _cleanup(now: float, ttl: float) -> None:
    if len(_buckets) <= _MAX_KEYS:
        return
    stale = [key for key, bucket in _buckets.items() if not bucket or now - bucket[-1] > ttl]
    for key in stale:
        _buckets.pop(key, None)


def rate_limit(scope: str, *, times: int, seconds: float) -> Callable[[Request], Awaitable[None]]:
    """FastAPI-зависимость: не более `times` запросов за `seconds` секунд с одного IP."""

    async def dependency(request: Request) -> None:
        if not settings.auth_rate_limit_enabled:
            return
        now = time.monotonic()
        bucket = _buckets[(scope, _client_ip(request))]
        while bucket and now - bucket[0] > seconds:
            bucket.popleft()
        if len(bucket) >= times:
            raise errors.rate_limited()
        bucket.append(now)
        _cleanup(now, seconds)

    return dependency
