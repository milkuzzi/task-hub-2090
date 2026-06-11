"""Тексты уведомлений (рус.) для 4 событий и двух ролей (§9, §13.4.3).

Чистые функции: на вход — реквизиты задачи, на выход — (тема, текст).
Тема используется e-mail-каналом; MAX её игнорирует.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskBrief:
    seq_no: int
    code: str
    title: str
    description: str
    due_display: str  # отформатированный срок (дата или дата+время)


def _footer(task: TaskBrief) -> str:
    parts = [f"\n\nЗадача №{task.seq_no} (код для поиска: {task.code})", f"Название: {task.title}"]
    if task.description:
        parts.append(f"Описание: {task.description}")
    parts.append(f"Срок: {task.due_display}")
    return "\n".join(parts)


def assigned_executor(task: TaskBrief) -> tuple[str, str]:
    subject = f"Вам поставлена задача №{task.seq_no}"
    body = f"Вам поставлена задача №{task.seq_no} (вы назначены исполнителем)." + _footer(task)
    return subject, body


def assigned_observer(task: TaskBrief) -> tuple[str, str]:
    subject = f"Вы назначены наблюдателем по задаче №{task.seq_no}"
    body = f"Вы назначены наблюдателем по задаче №{task.seq_no}." + _footer(task)
    return subject, body


def due_tomorrow(task: TaskBrief) -> tuple[str, str]:
    subject = f"Завтра истекает срок задачи №{task.seq_no}"
    body = f"Завтра истекает срок исполнения поручения №{task.seq_no}." + _footer(task)
    return subject, body


def due_today(task: TaskBrief) -> tuple[str, str]:
    subject = f"Сегодня истекает срок задачи №{task.seq_no}"
    body = f"Срок вашей задачи №{task.seq_no} истекает сегодня." + _footer(task)
    return subject, body


def overdue_daily(task: TaskBrief) -> tuple[str, str]:
    subject = f"Задача №{task.seq_no} просрочена"
    body = (
        f"Задача №{task.seq_no} просрочена. Срок истёк ({task.due_display}). "
        f"Пожалуйста, завершите её или сообщите постановщику." + _footer(task)
    )
    return subject, body
