"""Real-time транспорт: in-process реестр WebSocket-соединений (§транспорт)."""

from app.realtime.manager import ConnectionManager, manager

__all__ = ["ConnectionManager", "manager"]
