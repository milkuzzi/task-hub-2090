"""Роутер аутентификации и сброса пароля (§13.5.4).

refresh-токен живёт в httpOnly+Secure+SameSite=Strict cookie; access — в теле ответа.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginIn,
    ResetConfirmIn,
    ResetRequestIn,
    TokenOut,
    UserOut,
)
from app.schemas.common import OkResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"
_REFRESH_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        _REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_ttl_days * 86400,
        httponly=True,
        secure=settings.is_prod,
        samesite="strict",
        path=_REFRESH_PATH,
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, is_admin=user.is_admin, display_name=user.display_name
    )


@router.post(
    "/login",
    response_model=TokenOut,
    dependencies=[Depends(rate_limit("login", times=10, seconds=60))],
)
async def login(body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    user, access, raw = await auth_service.login(db, email=body.email, password=body.password)
    _set_refresh_cookie(response, raw)
    return TokenOut(access_token=access, user=_user_out(user))


@router.post("/refresh", response_model=TokenOut)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(_REFRESH_COOKIE)
    user, access, new_raw = await auth_service.refresh(db, raw_refresh=raw)
    _set_refresh_cookie(response, new_raw)
    return TokenOut(access_token=access, user=_user_out(user))


@router.post("/logout", response_model=OkResponse)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    raw = request.cookies.get(_REFRESH_COOKIE)
    await auth_service.logout(db, raw_refresh=raw)
    response.delete_cookie(_REFRESH_COOKIE, path=_REFRESH_PATH)
    return OkResponse()


@router.post(
    "/password-reset/request",
    response_model=OkResponse,
    # Жёстче остальных: каждая попытка — реальное письмо через SMTP.
    dependencies=[Depends(rate_limit("reset_request", times=5, seconds=900))],
)
async def reset_request(body: ResetRequestIn, db: AsyncSession = Depends(get_db)):
    await auth_service.request_password_reset(db, email=body.email)
    return OkResponse()


@router.post(
    "/password-reset/confirm",
    response_model=OkResponse,
    dependencies=[Depends(rate_limit("reset_confirm", times=10, seconds=60))],
)
async def reset_confirm(body: ResetConfirmIn, db: AsyncSession = Depends(get_db)):
    await auth_service.confirm_password_reset(db, token=body.token, new_password=body.new_password)
    return OkResponse()


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser = Depends(get_current_user)):
    return UserOut(
        id=user.id, email=user.email, is_admin=user.is_admin, display_name=user.display_name
    )
