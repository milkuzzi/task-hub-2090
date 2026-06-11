"""Роутер справочника пользователей — для выбора исполнителя/наблюдателей (§4).

Доступен любому аутентифицированному пользователю (не админ-функция): отдаёт
только обезличенный публичный профиль (id, e-mail, имя), без приватных данных.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.api.presenters import user_ref
from app.db.session import get_db
from app.repositories import users_repo
from app.schemas.common import UserRefOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRefOut])
async def list_users(
    query: str | None = Query(default=None),
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    users = await users_repo.list_active(db, query)
    return [user_ref(u) for u in users]
