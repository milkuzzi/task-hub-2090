"""Интеграция: создание задачи с вложениями (№6, Requirement 1).

Контракт `POST /tasks` — `multipart/form-data`: поле `payload` (JSON-строка с
телом задачи) + ноль или более `files`. Проверяем:
  - создание с N файлами: задача и файловые вложения сохранены, файлы на диске;
  - нарушение лимита: задача НЕ создаётся, файлы в сторадж НЕ записаны (атомарность);
  - создание без файлов по-прежнему работает (обратная совместимость);
  - создание со ссылочными вложениями (links).
"""

from __future__ import annotations

from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from sqlalchemy import func, select

import app.storage.base as storage_base
from app.core.clock import now
from app.core.config import settings
from app.domain.enums import DueMode
from app.models import Task, TaskAttachment
from app.schemas.tasks import TaskCreateIn
from app.services import task_service
from app.storage.base import LocalStorage
from tests.factories import auth_header, create_task_form, current_of, make_user


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Хранилище в tmp-каталоге вместо тома /data."""
    monkeypatch.setattr(storage_base, "_storage", LocalStorage(root=str(tmp_path)))
    yield Path(tmp_path)
    monkeypatch.setattr(storage_base, "_storage", None)


def _payload(assignee_id, **over):
    base = {
        "title": "Задача с файлами",
        "dueAt": (now() + timedelta(days=2)).isoformat(),
        "dueMode": "datetime",
        "assigneeIds": [str(assignee_id)],
        "observerIds": [],
        "links": [],
    }
    base.update(over)
    return base


async def _count_attachments(db, task_id) -> int:
    res = await db.execute(
        select(func.count()).select_from(TaskAttachment).where(TaskAttachment.task_id == task_id)
    )
    return res.scalar_one()


def _all_files_in(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


async def test_create_with_files_persists_task_and_attachments(client, db, tmp_storage):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    files = [
        ("files", ("one.txt", b"hello one", "text/plain")),
        ("files", ("two.bin", b"\x00\x01\x02 binary", "application/octet-stream")),
    ]
    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(_payload(assignee.id)),
        files=files,
        headers=auth_header(author),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    task_id = body["id"]
    # Два файловых вложения в карточке.
    file_atts = [a for a in body["attachments"] if a["kind"] == "file"]
    assert len(file_atts) == 2
    assert {a["filename"] for a in file_atts} == {"one.txt", "two.bin"}

    # Вложения персистентны в БД.
    assert await _count_attachments(db, task_id) == 2
    # Файлы реально записаны на диск тестового стораджа.
    on_disk = _all_files_in(tmp_storage)
    assert len(on_disk) == 2
    assert sum(p.stat().st_size for p in on_disk) == len(b"hello one") + len(b"\x00\x01\x02 binary")


async def test_create_without_files_still_works(client, db, tmp_storage):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(_payload(assignee.id)),
        headers=auth_header(author),
    )
    assert r.status_code == 201, r.text
    assert r.json()["attachments"] == []
    assert _all_files_in(tmp_storage) == []


async def test_create_with_link_attachments(client, db, tmp_storage):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    payload = _payload(assignee.id, links=["https://example.com/spec", "http://example.org/x"])
    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(payload),
        headers=auth_header(author),
    )
    assert r.status_code == 201, r.text
    urls = {a["url"] for a in r.json()["attachments"] if a["kind"] == "url"}
    assert urls == {"https://example.com/spec", "http://example.org/x"}
    # Ссылки не создают файлов на диске.
    assert _all_files_in(tmp_storage) == []


async def test_create_with_files_and_links_together(client, db, tmp_storage):
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    payload = _payload(assignee.id, links=["https://example.com/doc"])
    files = [("files", ("a.txt", b"data", "text/plain"))]
    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(payload),
        files=files,
        headers=auth_header(author),
    )
    assert r.status_code == 201, r.text
    kinds = sorted(a["kind"] for a in r.json()["attachments"])
    assert kinds == ["file", "url"]
    assert len(_all_files_in(tmp_storage)) == 1


async def test_total_size_limit_creates_nothing(client, db, tmp_storage, monkeypatch):
    """Нарушение суммарного лимита: ни задачи, ни файлов (атомарность, Req 1.5)."""
    monkeypatch.setattr(settings, "max_task_total_mb", 1)
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    before = (await db.execute(select(func.count()).select_from(Task))).scalar_one()

    # Два файла по 700 КБ — суммарно > 1 МБ.
    files = [
        ("files", ("big1.bin", b"x" * (700 * 1024), "application/octet-stream")),
        ("files", ("big2.bin", b"y" * (700 * 1024), "application/octet-stream")),
    ]
    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(_payload(assignee.id)),
        files=files,
        headers=auth_header(author),
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "TASK_TOTAL_SIZE_LIMIT"

    # Задача не создана и файлы не записаны (нет «осиротевших»).
    after = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    assert after == before
    assert _all_files_in(tmp_storage) == []


async def test_file_count_limit_creates_nothing(client, db, tmp_storage, monkeypatch):
    """Превышение числа файлов на задачу: ничего не создаётся."""
    monkeypatch.setattr(settings, "max_files_per_task", 2)
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    before = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    files = [
        ("files", (f"f{i}.txt", b"data", "text/plain")) for i in range(3)
    ]
    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(_payload(assignee.id)),
        files=files,
        headers=auth_header(author),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "ATTACHMENTS_LIMIT"

    after = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    assert after == before
    assert _all_files_in(tmp_storage) == []


async def test_empty_filename_rejected_creates_nothing(client, db, tmp_storage):
    """Пустое имя файла → 415, задача не создаётся."""
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    before = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    files = [("files", ("   ", b"data", "application/octet-stream"))]
    r = await client.post(
        "/api/v1/tasks",
        data=create_task_form(_payload(assignee.id)),
        files=files,
        headers=auth_header(author),
    )
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "UNSUPPORTED_FILENAME"

    after = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    assert after == before
    assert _all_files_in(tmp_storage) == []


class _FailingStorage(LocalStorage):
    """Сторадж, падающий на N-м вызове save (имитация сбоя записи на диск)."""

    def __init__(self, root: str, *, fail_on: int) -> None:
        super().__init__(root=root)
        self._calls = 0
        self._fail_on = fail_on

    def save(self, task_id, data):  # type: ignore[override]
        self._calls += 1
        if self._calls >= self._fail_on:
            raise RuntimeError("disk full simulation")
        return super().save(task_id, data)


async def test_storage_failure_compensates_written_files(db, tmp_path, monkeypatch):
    """Сбой записи второго файла → откат задачи + удаление уже записанного файла.

    Файл №1 успешно попал на диск, на файле №2 сторадж падает. Компенсация в
    task_service удаляет записанный файл №1, транзакция откатывается — не остаётся
    ни задачи, ни «осиротевших» файлов (Req 1.5, correctness property №5).

    Проверяем на уровне сервиса: транспортный слой 500-х ошибок здесь не важен,
    важна доменная гарантия атомарности/компенсации.
    """
    monkeypatch.setattr(
        storage_base, "_storage", _FailingStorage(str(tmp_path), fail_on=2)
    )
    author = await make_user(db, "a@s.ru")
    assignee = await make_user(db, "b@s.ru")
    await db.commit()

    before = (await db.execute(select(func.count()).select_from(Task))).scalar_one()

    data = TaskCreateIn(
        title="Задача со сбоем",
        due_at=now() + timedelta(days=2),
        due_mode=DueMode.DATETIME,
        assignee_ids=[assignee.id],
        observer_ids=[],
        links=[],
    )
    uploads = [
        UploadFile(file=BytesIO(b"first file"), filename="one.txt"),
        UploadFile(file=BytesIO(b"second file"), filename="two.txt"),
    ]
    with pytest.raises(RuntimeError):
        await task_service.create_task(db, current_of(author), data, files=uploads)

    monkeypatch.setattr(storage_base, "_storage", None)
    after = (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    assert after == before
    # Уже записанный файл №1 удалён компенсацией — на диске пусто.
    assert _all_files_in(tmp_path) == []

