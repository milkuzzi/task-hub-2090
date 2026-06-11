"""Абстракция хранилища вложений (§13.5.6).

Файлы лежат как непрозрачные объекты: на диске имя = UUID вложения, без исходного
имени и расширения (исключает path-traversal). Исходное имя и MIME — в БД.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class StoredFile:
    stored_key: str  # относительный путь "<task_id>/<attachment_uuid>"
    size: int
    sha256: str


class StorageBackend(Protocol):
    def save(self, task_id: uuid.UUID, data: bytes) -> StoredFile: ...

    def path_of(self, stored_key: str) -> Path: ...

    def delete(self, stored_key: str) -> None: ...

    def delete_task_dir(self, task_id: uuid.UUID) -> None: ...

    def delete_many(self, stored_keys: list[str]) -> None: ...


class LocalStorage:
    """Хранилище на локальном томе (по умолчанию)."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.attachments_dir)

    def save(self, task_id: uuid.UUID, data: bytes) -> StoredFile:
        att_uuid = uuid.uuid4().hex
        task_dir = self.root / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        dest = task_dir / att_uuid
        dest.write_bytes(data)
        return StoredFile(
            stored_key=f"{task_id}/{att_uuid}",
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    def path_of(self, stored_key: str) -> Path:
        # stored_key полностью контролируется сервером (UUID/UUID), traversal невозможен
        return self.root / stored_key

    def delete(self, stored_key: str) -> None:
        try:
            self.path_of(stored_key).unlink(missing_ok=True)
        except OSError:
            pass

    def delete_task_dir(self, task_id: uuid.UUID) -> None:
        shutil.rmtree(self.root / str(task_id), ignore_errors=True)

    def delete_many(self, stored_keys: list[str]) -> None:
        for key in stored_keys:
            self.delete(key)


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage
