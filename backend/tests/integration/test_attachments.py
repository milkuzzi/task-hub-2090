"""Интеграция: лимит суммарного размера вложений задачи (§M3).

Проверяет, что суммарный объём файловых вложений задачи ограничен
MAX_TASK_TOTAL_MB: загрузка, выводящая сумму за предел, отклоняется (413).
"""

from __future__ import annotations

import pytest

import app.storage.base as storage_base
from app.core.config import settings
from app.storage.base import LocalStorage
from tests.factories import auth_header, make_task, make_user


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Хранилище в tmp-каталоге вместо тома /data, чтобы тест не писал на боевой путь."""
    monkeypatch.setattr(storage_base, "_storage", LocalStorage(root=str(tmp_path)))
    yield
    monkeypatch.setattr(storage_base, "_storage", None)


async def test_task_total_size_limit_enforced(client, db, tmp_storage, monkeypatch):
    # Предел — 1 МБ суммарно на задачу.
    monkeypatch.setattr(settings, "max_task_total_mb", 1)
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    task = await make_task(db, author, assignee)
    await db.commit()

    headers = auth_header(author)
    # Первый файл 600 КБ — проходит.
    first = b"x" * (600 * 1024)
    r1 = await client.post(
        f"/api/v1/tasks/{task.id}/attachments",
        files={"file": ("a.bin", first, "application/octet-stream")},
        headers=headers,
    )
    assert r1.status_code == 201

    # Второй файл 600 КБ — суммарно >1 МБ, отклоняется.
    second = b"y" * (600 * 1024)
    r2 = await client.post(
        f"/api/v1/tasks/{task.id}/attachments",
        files={"file": ("b.bin", second, "application/octet-stream")},
        headers=headers,
    )
    assert r2.status_code == 413
    assert r2.json()["error"]["code"] == "TASK_TOTAL_SIZE_LIMIT"


async def test_under_total_limit_allowed(client, db, tmp_storage, monkeypatch):
    monkeypatch.setattr(settings, "max_task_total_mb", 1)
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    task = await make_task(db, author, assignee)
    await db.commit()

    data = b"z" * (200 * 1024)
    r = await client.post(
        f"/api/v1/tasks/{task.id}/attachments",
        files={"file": ("ok.bin", data, "application/octet-stream")},
        headers=auth_header(author),
    )
    assert r.status_code == 201
