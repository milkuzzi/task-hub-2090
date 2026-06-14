"""Чат задачи и on-site уведомления (BLOCK 2 спеки task-collaboration).

В этой ревизии:
  (a) Таблица `task_messages` — сообщения чата задачи (автор RESTRICT, тело
      ограничено по длине на уровне приложения) + индекс (task_id, created_at);
  (b) Таблица `notifications` — on-site уведомления пользователю (чат/доработка),
      ссылки на задачу и сообщение каскадно зануляются вместе с ними + индекс
      (user_id, is_read, created_at DESC) под выборку «непрочитанные сверху».

WebSocket-доставка — рантайм-канал, схемы не требует. E-mail по этим событиям не
шлётся (отдельный on-site канал).

Revision ID: 0004_chat_notifications
Revises: 0003_collaboration
Create Date: 2026-06-14
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004_chat_notifications"
down_revision: str | None = "0003_collaboration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (a) Сообщения чата. author_id RESTRICT — нельзя удалить пользователя,
    #     оставив осиротевшие сообщения (актуальное имя показываем по join).
    op.execute(
        """
        CREATE TABLE task_messages (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id    UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            author_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            body       TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_task_messages_task ON task_messages(task_id, created_at)"
    )

    # (b) Уведомления. user_id CASCADE — уведомления исчезают вместе с адресатом.
    #     task_id/message_id NULL + CASCADE — событие может пережить ссылку, но
    #     при удалении задачи/сообщения связанные уведомления тоже удаляются.
    op.execute(
        """
        CREATE TABLE notifications (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind       TEXT NOT NULL,
            task_id    UUID REFERENCES tasks(id) ON DELETE CASCADE,
            message_id UUID REFERENCES task_messages(id) ON DELETE CASCADE,
            text       TEXT NOT NULL,
            is_read    BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_notifications_user_unread "
        "ON notifications(user_id, is_read, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS task_messages CASCADE")
