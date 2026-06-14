"""In-process реестр активных WebSocket-соединений (design.md «Транспорт»).

`ConnectionManager` хранит соответствие `user_id -> {WebSocket}` и умеет
рассылать payload набору пользователей. Реализация однопроцессная: при единственном
backend-контейнере этого достаточно.

ЗАДЕЛ: при горизонтальном масштабировании (несколько backend-процессов) доставку
между процессами нужно вынести в Redis pub/sub — тогда `send_to_users` публикует
в канал, а каждый процесс рассылает своим локальным сокетам. Здесь намеренно
оставлен in-process вариант.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Iterable
from typing import Any, Protocol
from uuid import UUID

log = logging.getLogger("app.realtime")


class WebSocketLike(Protocol):
    """Минимальный контракт сокета (Starlette WebSocket / тестовый фейк)."""

    async def send_json(self, data: Any) -> None: ...


class ConnectionManager:
    """Потокобезопасный (в рамках одного event loop) реестр соединений."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocketLike]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, ws: WebSocketLike) -> None:
        async with self._lock:
            self._connections[user_id].add(ws)

    async def disconnect(self, user_id: UUID, ws: WebSocketLike) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            sockets.discard(ws)
            if not sockets:
                self._connections.pop(user_id, None)

    def is_connected(self, user_id: UUID) -> bool:
        return bool(self._connections.get(user_id))

    async def send_to_users(self, user_ids: Iterable[UUID], payload: dict[str, Any]) -> None:
        """Рассылает payload всем активным сокетам перечисленных пользователей.

        Дубли user_id схлопываются. Ошибка отправки на один сокет (обрыв) не
        срывает доставку остальным — «мёртвый» сокет будет вычищен на disconnect.
        """
        unique_ids = set(user_ids)
        targets: list[tuple[UUID, WebSocketLike]] = []
        for uid in unique_ids:
            for ws in list(self._connections.get(uid, ())):
                targets.append((uid, ws))
        for uid, ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 — обрыв соединения не должен ронять рассылку
                log.debug("Не удалось доставить payload по WS пользователю %s", uid)


# Module-level singleton — общий реестр на процесс.
manager = ConnectionManager()
