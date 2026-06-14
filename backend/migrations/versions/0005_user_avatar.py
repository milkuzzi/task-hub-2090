"""Аватар пользователя в профиле (BLOCK 4 спеки task-collaboration, №8).

В этой ревизии:
  `ALTER TABLE users ADD COLUMN avatar_path TEXT` — ключ файла-аватара в сторадже
  вложений (UUID-имя объекта). NULL = аватар не загружен (фронт рисует инициалы).
  Контакт MAX (`email_registry.max_user_id`) уже существует и становится
  редактируемым самим пользователем через `PATCH /users/me` — схема не меняется.

Revision ID: 0005_user_avatar
Revises: 0004_chat_notifications
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_user_avatar"
down_revision: str | None = "0004_chat_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN avatar_path TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN avatar_path")
