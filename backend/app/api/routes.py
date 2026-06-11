"""Единый источник базового префикса API и хелперов путей (§13.5.1)."""

from __future__ import annotations

import uuid

API_PREFIX = "/api/v1"


def attachment_download_path(task_id: uuid.UUID, att_id: uuid.UUID) -> str:
    return f"{API_PREFIX}/tasks/{task_id}/attachments/{att_id}/download"
