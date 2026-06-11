"""Интеграция: сквозная нумерация без дыр + 6-значный код с ретраем (§13.7.3 Б/В)."""

from __future__ import annotations

import app.repositories.tasks_repo as tasks_repo
from tests.factories import make_task, make_user


async def test_gapless_sequential_numbering(db):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    tasks = [await make_task(db, a, b, title=f"T{i}") for i in range(5)]
    nos = [t.task_no for t in tasks]
    # строго последовательно, без дыр и дублей (в пределах одной транзакции теста)
    assert nos == list(range(nos[0], nos[0] + 5))
    assert len(set(nos)) == 5


async def test_code6_range_and_uniqueness(db):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    codes = [(await make_task(db, a, b)).code6 for _ in range(8)]
    assert all(100000 <= c <= 999999 for c in codes)
    assert len(set(codes)) == 8


async def test_code6_collision_retry(db, monkeypatch):
    a = await make_user(db, "a@s.ru")
    b = await make_user(db, "b@s.ru")
    first = await make_task(db, a, b)
    taken = first.code6
    free = 555555 if taken != 555555 else 444444

    # первая генерация отдаёт занятый код → повтор → свободный
    seq = iter([taken - 100000, free - 100000])
    monkeypatch.setattr(tasks_repo.secrets, "randbelow", lambda n: next(seq))
    second = await make_task(db, a, b)
    assert second.code6 == free
    assert second.code6 != taken
