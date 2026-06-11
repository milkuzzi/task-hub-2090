"""Роутер администрирования реестра (только админ) (§13.5.4)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_admin
from app.core import errors
from app.db.session import get_db
from app.schemas.admin import (
    RegistryCreateIn,
    RegistryItemOut,
    RegistryListResponse,
    RegistryUpdateIn,
    UserDeleteResult,
)
from app.schemas.common import OkResponse
from app.services import registry_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/registry", response_model=RegistryListResponse)
async def list_registry(
    query: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    _: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await registry_service.list_registry(
        db, query=query, page=page, page_size=page_size
    )
    return RegistryListResponse(items=items, total=total)


@router.post("/registry", response_model=RegistryItemOut, status_code=201)
async def create_registry(
    body: RegistryCreateIn,
    _: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await registry_service.create_entry(db, body)


@router.put("/registry/{entry_id}", response_model=RegistryItemOut)
async def update_registry(
    entry_id: uuid.UUID,
    body: RegistryUpdateIn,
    _: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await registry_service.update_entry(db, entry_id, body)


@router.delete("/registry/{entry_id}", response_model=OkResponse)
async def delete_registry(
    entry_id: uuid.UUID,
    _: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await registry_service.delete_entry(db, entry_id)
    return OkResponse()


@router.delete("/users/{user_id}", response_model=UserDeleteResult)
async def delete_user(
    user_id: uuid.UUID,
    confirm: bool = Query(default=False),
    actor: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not confirm:
        # серверная страховка под диалог подтверждения (§13.5.4)
        raise errors.bad_request("Требуется подтверждение: confirm=true.")
    return await registry_service.delete_user_and_archive(db, user_id, actor)
