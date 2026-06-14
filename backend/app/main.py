"""Сборка FastAPI-приложения: роутеры, единый обработчик ошибок, CORS,
security-заголовки (§13.3, §13.5.2, §13.7.4)."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import admin, auth, tasks, users
from app.api.routes import API_PREFIX
from app.core import errors
from app.core.config import settings

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Опционально: планировщик внутри backend-процесса (3 контейнера вместо 4).
    scheduler = None
    if settings.scheduler_in_process:
        from app.scheduler import build_scheduler

        scheduler = build_scheduler()
        scheduler.start()
        log.info("Планировщик запущен внутри backend-процесса (SCHEDULER_IN_PROCESS=true)")
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="Система поручений — школа № 2090",
    version="1.0.0",
    docs_url=f"{API_PREFIX}/docs",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)


# --- Единый обработчик ошибок (§13.5.2) ---


@app.exception_handler(errors.AppError)
async def app_error_handler(_: Request, exc: errors.AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_body())


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "")}
        for e in exc.errors()
    ]
    err = errors.validation_error(details)
    return JSONResponse(status_code=err.status_code, content=err.to_body())


# --- Security-заголовки (чистый ASGI-middleware, без BaseHTTPMiddleware) ---


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-content-type-options", b"nosniff"))
                headers.append((b"x-frame-options", b"DENY"))
                headers.append((b"referrer-policy", b"no-referrer"))
                if settings.is_prod:
                    headers.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
            await send(message)

        await self.app(scope, receive, send_wrapper)


class RequestIDMiddleware:
    """Сквозной идентификатор запроса для диагностики без DevOps.

    Берёт входящий `X-Request-ID` (от внешнего прокси/туннеля) либо генерирует
    новый и возвращает его в ответе. Помогает связать строки логов одного запроса.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or {})
        rid = incoming.get(b"x-request-id")
        request_id = rid.decode("latin-1") if rid else uuid.uuid4().hex

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((b"x-request-id", request_id.encode("latin-1")))
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Роутеры ---

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)


@app.get(f"{API_PREFIX}/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
