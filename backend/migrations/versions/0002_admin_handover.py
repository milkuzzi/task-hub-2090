"""Передача администрирования: nullable password_hash + отложенный handover.

(a) `users.password_hash` становится nullable — приглашённый пользователь без
    пароля (неактивированная учётка) не может войти, пока не задаст пароль.
(b) Таблица `pending_admin_handover` фиксирует намерение передать
    администрирование; понижение исходящего админа происходит при активации
    входящего (§ Требование 2).

Revision ID: 0002_admin_handover
Revises: 0001_initial
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_admin_handover"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # (a) Разрешаем NULL — учётка может существовать до установки пароля.
    op.execute("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")

    # (b) Таблица отложенной передачи администрирования.
    op.execute(
        """
        CREATE TABLE pending_admin_handover (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            incoming_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            outgoing_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Не более одной ожидающей передачи на входящего администратора.
    op.execute(
        "CREATE UNIQUE INDEX uq_pending_handover_incoming "
        "ON pending_admin_handover(incoming_user_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pending_admin_handover CASCADE")
    # Перед возвратом NOT NULL заполняем возможные NULL пустой строкой.
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.execute("ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL")
