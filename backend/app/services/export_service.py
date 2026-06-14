"""Выгрузка текущего списка под печать — самодостаточная HTML-страница (§13.5.5).

Использует тот же слой выборки, что и `GET /tasks`, чтобы экспорт и список не
расходились. Jinja2 с включённым autoescape (защита от инъекций из названий/отчётов).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.clock import now, to_org_tz
from app.domain.enums import STATUS_LABELS_RU, DueMode, TaskStatus
from app.domain.overdue import is_overdue
from app.domain.status import is_open
from app.services import task_service

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2"]),
)

_ROLE_LABELS = {
    "author": "Я постановщик",
    "assignee": "Я исполнитель",
    "observer": "Я наблюдатель",
}


def _due_display(task) -> str:
    dt = to_org_tz(task.due_at)
    if task.due_mode == DueMode.DATETIME:
        return dt.strftime("%d.%m.%Y %H:%M")
    return dt.strftime("%d.%m.%Y")


def _effective_overdue(task) -> bool:
    if task.is_overdue:
        return True
    if is_open(task.status):
        return is_overdue(now(), task.due_at, task.due_mode)
    return False


async def render_print(
    db: AsyncSession,
    current: CurrentUser,
    *,
    role: str,
    status_filter: TaskStatus | None,
    sort: str | None,
    order: str,
) -> str:
    tasks, _total = await task_service.list_tasks(
        db,
        current,
        role=role,
        status_filter=status_filter,
        sort=sort,
        order=order,
        page=1,
        page_size=10000,
    )
    rows = []
    for t in tasks:
        rows.append(
            {
                "seq_no": t.task_no,
                "code": f"{t.code6:06d}",
                "title": t.title,
                "description": t.description,
                "due_display": _due_display(t),
                "assignee": ", ".join(a.user.display_name for a in t.assignees),
                "author": t.author.display_name,
                "observers": ", ".join(o.display_name for o in t.observers),
                "status_label": STATUS_LABELS_RU[t.status],
                "is_overdue": _effective_overdue(t),
                "report_text": t.report.text if t.report else "",
                "ready": bool(t.report and t.report.ready_flag),
            }
        )
    template = _env.get_template("print.html.j2")
    return template.render(
        role_label=_ROLE_LABELS.get(role, role),
        generated_at=now().strftime("%d.%m.%Y %H:%M"),
        rows=rows,
    )
