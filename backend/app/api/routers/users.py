"""Роутер справочника пользователей и профиля (§4, §8).

Справочник (`GET /users`) доступен любому аутентифицированному — отдаёт лишь
обезличенный публичный профиль (id, e-mail, имя). Профиль (`/users/me`, аватары)
редактируется самим пользователем; раздача аватара (`GET /users/{id}/avatar`) —
любому аутентифицированному (для отображения в чате задачи).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.api.presenters import user_ref
from app.db.session import get_db
from app.repositories import users_repo
from app.schemas.common import UserRefOut
from app.schemas.profile import ProfileOut, ProfileUpdateIn
from app.services import profile_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRefOut])
async def list_users(
    query: str | None = Query(default=None),
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    users = await users_repo.list_active(db, query)
    return [user_ref(u) for u in users]


# --- Профиль (§8). Статические /me-пути объявлены ДО /{user_id}/avatar. ---


@router.get("/me", response_model=ProfileOut)
async def get_me(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.get_my_profile(db, user)


@router.patch("/me", response_model=ProfileOut)
async def update_me(
    body: ProfileUpdateIn,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.update_my_profile(db, user, body)


@router.put("/me/avatar", response_model=ProfileOut)
async def put_my_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.set_avatar(db, user, file)


@router.delete("/me/avatar", response_model=ProfileOut)
async def delete_my_avatar(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await profile_service.delete_avatar(db, user)


@router.get("/{user_id}/avatar")
async def get_user_avatar(
    user_id: uuid.UUID,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Картинка-аватар пользователя для любого аутентифицированного (чат задачи)."""
    avatar = await profile_service.get_avatar(db, user_id)
    return Response(
        content=avatar.data,
        media_type=avatar.content_type,
        # Аватар может меняться; запрещаем агрессивное кэширование промежуточными.
        headers={"Cache-Control": "private, max-age=0, must-revalidate"},
    )
