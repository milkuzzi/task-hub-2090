"""WS-эндпойнт: аутентификация ПЕРВЫМ сообщением + handshake (design.md).

Используем синхронный Starlette TestClient (поддерживает websocket_connect).
Проверку реестра/БД в success-кейсе подменяем (`_authenticate`), чтобы тест не
зависел от закоммиченных в отдельном соединении данных; невалидные кейсы бьют по
реальной логике (декод токена/тип первого сообщения).
"""

from __future__ import annotations

import uuid

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.api.routers.ws as ws_mod
from app.main import app


def test_ws_rejects_when_first_message_not_auth():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json({"type": "ping"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_rejects_invalid_token():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json({"type": "auth", "token": "not-a-jwt"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_auth_handshake_ready(monkeypatch):
    user_id = uuid.uuid4()

    async def _fake_auth(_token: str):
        return user_id

    monkeypatch.setattr(ws_mod, "_authenticate", _fake_auth)

    client = TestClient(app)
    with client.websocket_connect("/api/v1/ws") as ws:
        ws.send_json({"type": "auth", "token": "valid"})
        msg = ws.receive_json()
        assert msg == {"type": "ready"}
    # После выхода из контекста соединение закрыто и снято с регистрации.
    assert not ws_mod.manager.is_connected(user_id)
