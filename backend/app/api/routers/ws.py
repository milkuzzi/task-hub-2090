"""WebSocket-эндпойнт реального времени (design.md «Транспорт»).

Один канал `/ws` для чата и уведомлений. Аутентификация — ПЕРВЫМ СООБЩЕНИЕМ
(`{"type":"auth","token":"<access>"}`), а не через query-параметр: так токен не
попадает в логи прокси/истории браузера (см. раздел «Безопасность» в design.md).

Поток:
  1. accept();
  2. ждём первое сообщение `auth` в течение `_AUTH_TIMEOUT_SEC`;
  3. декодируем access-токен → пользователь (+ проверка членства в реестре);
  4. при ошибке/таймауте — close(1008);
  5. регистрируем сокет в `manager`, шлём `{"type":"ready"}`, слушаем входящие
     (ping/keepalive игнорируются), на обрыве — снимаем регистрацию.

Запись сообщений и смена статуса идут через REST (надёжность/валидация),
WS — только канал доставки сервер→клиент.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.db.session import SessionFactory
from app.realtime.manager import manager
from app.repositories import registry_repo, users_repo

log = logging.getLogger("app.realtime")

router = APIRouter(tags=["ws"])

# Код закрытия WS для нарушения политики (невалидный/просроченный токен).
_POLICY_VIOLATION = 1008
# Сколько ждём первое auth-сообщение, прежде чем закрыть соединение.
_AUTH_TIMEOUT_SEC = 10.0


async def _authenticate(token: str) -> uuid.UUID | None:
    """Возвращает user_id, если токен валиден И пользователь в реестре, иначе None."""
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
    async with SessionFactory() as db:
        user = await users_repo.get_active_by_id(db, user_id)
        if user is None or not await registry_repo.is_listed(db, user.email):
            return None
    return user.id


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()

    # 1. Первое сообщение должно быть auth — с таймаутом, чтобы не держать
    #    незавершённые соединения.
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=_AUTH_TIMEOUT_SEC)
    except (TimeoutError, WebSocketDisconnect):
        await ws.close(code=_POLICY_VIOLATION)
        return
    except Exception:  # noqa: BLE001 — не-JSON / битый кадр
        await ws.close(code=_POLICY_VIOLATION)
        return

    token = first.get("token") if isinstance(first, dict) else None
    if not isinstance(first, dict) or first.get("type") != "auth" or not token:
        await ws.close(code=_POLICY_VIOLATION)
        return

    user_id = await _authenticate(token)
    if user_id is None:
        await ws.close(code=_POLICY_VIOLATION)
        return

    # 2. Регистрируем соединение и подтверждаем готовность.
    await manager.connect(user_id, ws)
    try:
        await ws.send_json({"type": "ready"})
    except Exception:  # noqa: BLE001
        await manager.disconnect(user_id, ws)
        return

    # 3. Слушаем входящие. Клиент шлёт только keepalive/ping — игнорируем тело;
    #    смысл цикла — детектировать обрыв и вычистить регистрацию.
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.debug("WS-соединение пользователя %s завершилось с ошибкой", user_id)
    finally:
        await manager.disconnect(user_id, ws)
