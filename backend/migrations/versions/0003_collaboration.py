"""Совместная работа над задачей (часть 1): мульти-исполнители и статусы проверки.

В этой ревизии (BLOCK 1 спеки task-collaboration):
  (a) Новые значения ENUM `task_status`: `under_review`, `rework`.
  (b) Таблица связей `task_assignees` (M:N задача↔исполнитель) + индекс по user_id;
      backfill из текущего одиночного `tasks.assignee_id`; затем столбец удаляется.

`ALTER TYPE ... ADD VALUE` в PostgreSQL не может выполняться внутри транзакции
(в части версий), поэтому выполняется в `autocommit_block()` — это делает шаг
безопасным независимо от того, что Alembic оборачивает миграцию в транзакцию.
`ADD VALUE IF NOT EXISTS` — идемпотентно (PG ≥ 12).

Таблицы `task_messages`, `notifications` и поле `users.avatar_path` добавятся
отдельными ревизиями в последующих блоках.

Revision ID: 0003_collaboration
Revises: 0002_admin_handover
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_collaboration"
down_revision: str | None = "0002_admin_handover"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (a) Новые значения статуса — вне транзакции (требование ALTER TYPE ADD VALUE).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'under_review'")
        op.execute("ALTER TYPE task_status ADD VALUE IF NOT EXISTS 'rework'")

    # (b) Таблица исполнителей (M:N). user_id RESTRICT сохраняет защиту: нельзя
    #     удалить пользователя с активными задачами (как было у assignee_id).
    op.execute(
        """
        CREATE TABLE task_assignees (
            task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            PRIMARY KEY (task_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_task_assignees_user ON task_assignees(user_id)")

    # Backfill: переносим текущего единственного исполнителя в новую модель.
    op.execute(
        "INSERT INTO task_assignees(task_id, user_id) SELECT id, assignee_id FROM tasks"
    )

    # Удаляем старый столбец (его индекс ix_tasks_assignee_due снимется каскадно).
    op.execute("ALTER TABLE tasks DROP COLUMN assignee_id")


def downgrade() -> None:
    # Восстанавливаем одиночного исполнителя из первой (по user_id) строки связи.
    # Значения ENUM удалить нельзя (PostgreSQL не поддерживает DROP VALUE) — это
    # документированное ограничение: под_review/rework останутся в типе.
    op.execute(
        "ALTER TABLE tasks ADD COLUMN assignee_id UUID REFERENCES users(id) ON DELETE RESTRICT"
    )
    op.execute(
        """
        UPDATE tasks t SET assignee_id = (
            SELECT ta.user_id FROM task_assignees ta
            WHERE ta.task_id = t.id
            ORDER BY ta.user_id
            LIMIT 1
        )
        """
    )
    # Закрываем возможные NULL (задачи без исполнителей) перед NOT NULL.
    op.execute("DELETE FROM tasks WHERE assignee_id IS NULL")
    op.execute("ALTER TABLE tasks ALTER COLUMN assignee_id SET NOT NULL")
    op.execute("CREATE INDEX ix_tasks_assignee_due ON tasks(assignee_id, due_at)")

    op.execute("DROP TABLE IF EXISTS task_assignees CASCADE")
