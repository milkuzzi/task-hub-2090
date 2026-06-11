"""DTO отчёта исполнителя и отметки готовности (§13.5.4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class ReportIn(CamelModel):
    text: str | None = Field(default=None, max_length=20000)


class MarkReadyIn(CamelModel):
    text: str | None = Field(default=None, max_length=20000)


class MarkReadyOut(CamelModel):
    ready: bool
    ready_at: datetime | None = None


class LinkIn(CamelModel):
    url: str = Field(min_length=1, max_length=2000)
