"""Unit: in-process реестр WebSocket-соединений (ConnectionManager)."""

from __future__ import annotations

import uuid

from app.realtime.manager import ConnectionManager
from tests.fakes import FakeSocket


async def test_connect_send_disconnect():
    mgr = ConnectionManager()
    uid = uuid.uuid4()
    ws = FakeSocket()

    await mgr.connect(uid, ws)
    assert mgr.is_connected(uid)

    await mgr.send_to_users([uid], {"type": "x"})
    assert ws.received == [{"type": "x"}]

    await mgr.disconnect(uid, ws)
    assert not mgr.is_connected(uid)

    # После отключения доставка — no-op.
    await mgr.send_to_users([uid], {"type": "y"})
    assert ws.received == [{"type": "x"}]


async def test_send_dedups_user_ids():
    mgr = ConnectionManager()
    uid = uuid.uuid4()
    ws = FakeSocket()
    await mgr.connect(uid, ws)
    # Дублирующиеся id не приводят к повторной доставке на тот же сокет.
    await mgr.send_to_users([uid, uid, uid], {"type": "once"})
    assert ws.received == [{"type": "once"}]


async def test_multiple_sockets_per_user():
    mgr = ConnectionManager()
    uid = uuid.uuid4()
    a, b = FakeSocket(), FakeSocket()
    await mgr.connect(uid, a)
    await mgr.connect(uid, b)
    await mgr.send_to_users([uid], {"type": "fanout"})
    assert a.received and b.received


async def test_dead_socket_does_not_break_delivery():
    mgr = ConnectionManager()
    u1, u2 = uuid.uuid4(), uuid.uuid4()
    dead = FakeSocket(fail=True)
    alive = FakeSocket()
    await mgr.connect(u1, dead)
    await mgr.connect(u2, alive)
    # Обрыв на одном сокете не мешает доставке другому.
    await mgr.send_to_users([u1, u2], {"type": "broadcast"})
    assert alive.received == [{"type": "broadcast"}]
