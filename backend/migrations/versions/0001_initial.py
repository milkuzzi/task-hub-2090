"""Начальная схема: реестр, пользователи, задачи, наблюдатели, вложения,
отчёты, журнал уведомлений, токены, счётчики; индексы и триггеры (§13.2, §13.4.3).

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- 1. Расширения и ENUM-типы (порядок критичен) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE TYPE task_status AS ENUM ('in_progress', 'done', 'cancelled')")
    op.execute("CREATE TYPE due_mode AS ENUM ('datetime', 'date')")
    op.execute("CREATE TYPE attach_kind AS ENUM ('file', 'url')")

    # --- 2. Таблицы (в порядке зависимостей FK) ---
    op.execute(
        """
        CREATE TABLE projects (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name       TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE email_registry (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email       CITEXT NOT NULL UNIQUE,
            full_name   TEXT,
            max_user_id TEXT,
            is_admin    BOOLEAN NOT NULL DEFAULT false,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE users (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email         CITEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin      BOOLEAN NOT NULL DEFAULT false,
            display_name  TEXT NOT NULL,
            is_deleted    BOOLEAN NOT NULL DEFAULT false,
            deleted_at    TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tasks (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_no            BIGINT NOT NULL UNIQUE,
            code6              INTEGER NOT NULL UNIQUE,
            title              TEXT NOT NULL,
            description        TEXT,
            due_at             TIMESTAMPTZ NOT NULL,
            due_mode           due_mode NOT NULL DEFAULT 'datetime',
            due_version        INTEGER NOT NULL DEFAULT 1,
            status             task_status NOT NULL DEFAULT 'in_progress',
            is_overdue         BOOLEAN NOT NULL DEFAULT false,
            overdue_since      TIMESTAMPTZ,
            needs_reassignment BOOLEAN NOT NULL DEFAULT false,
            author_id          UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            assignee_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            project_id         UUID REFERENCES projects(id) ON DELETE SET NULL,
            created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_tasks_title_not_blank CHECK (char_length(btrim(title)) > 0),
            CONSTRAINT ck_tasks_code6_range CHECK (code6 BETWEEN 100000 AND 999999)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE task_observers (
            task_id      UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            display_name TEXT NOT NULL,
            added_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (task_id, user_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE task_attachments (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id       UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            kind          attach_kind NOT NULL,
            file_path     TEXT,
            original_name TEXT,
            mime_type     TEXT,
            size_bytes    BIGINT,
            url           TEXT,
            uploaded_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_task_attach_kind CHECK (
                (kind = 'file' AND file_path IS NOT NULL AND url IS NULL)
             OR (kind = 'url'  AND url IS NOT NULL AND file_path IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE task_reports (
            task_id    UUID PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
            text       TEXT,
            ready_flag BOOLEAN NOT NULL DEFAULT false,
            ready_at   TIMESTAMPTZ,
            updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE report_attachments (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id       UUID NOT NULL REFERENCES task_reports(task_id) ON DELETE CASCADE,
            kind          attach_kind NOT NULL,
            file_path     TEXT,
            original_name TEXT,
            mime_type     TEXT,
            size_bytes    BIGINT,
            url           TEXT,
            uploaded_by   UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_report_attach_kind CHECK (
                (kind = 'file' AND file_path IS NOT NULL AND url IS NULL)
             OR (kind = 'url'  AND url IS NOT NULL AND file_path IS NULL))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE notification_log (
            id           BIGSERIAL PRIMARY KEY,
            task_id      UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            event_type   TEXT NOT NULL,
            recipient_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            due_version  INTEGER,
            run_date     DATE,
            email_status TEXT NOT NULL,
            max_status   TEXT NOT NULL,
            detail       TEXT,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE password_reset_tokens (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at    TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE counters (
            name  TEXT PRIMARY KEY,
            value BIGINT NOT NULL DEFAULT 0
        )
        """
    )

    # --- 3. Индексы (списки, сортировки, планировщик) ---
    op.execute("CREATE INDEX ix_observers_user ON task_observers(user_id)")
    op.execute("CREATE INDEX ix_task_attach_task ON task_attachments(task_id)")
    op.execute("CREATE INDEX ix_report_attach_task ON report_attachments(task_id)")
    op.execute("CREATE INDEX ix_tasks_author_due ON tasks(author_id, due_at)")
    op.execute("CREATE INDEX ix_tasks_assignee_due ON tasks(assignee_id, due_at)")
    op.execute(
        "CREATE INDEX ix_tasks_open_due ON tasks(due_at) WHERE status = 'in_progress'"
    )
    op.execute(
        "CREATE INDEX ix_tasks_overdue ON tasks(is_overdue) "
        "WHERE is_overdue = true AND status = 'in_progress'"
    )
    op.execute("CREATE INDEX ix_reset_user ON password_reset_tokens(user_id)")
    op.execute("CREATE INDEX ix_refresh_user ON refresh_tokens(user_id)")

    # Идемпотентность уведомлений (§13.4.3)
    op.execute(
        "CREATE UNIQUE INDEX uq_notif_dated ON notification_log "
        "(task_id, event_type, recipient_id, due_version, run_date) "
        "WHERE run_date IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_notif_assigned ON notification_log "
        "(task_id, event_type, recipient_id) WHERE event_type = 'assigned'"
    )

    # --- 4. Функции и триггеры ---
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END $$ LANGUAGE plpgsql
        """
    )
    for tbl in ("tasks", "users", "email_registry", "task_reports"):
        op.execute(
            f"CREATE TRIGGER {tbl}_touch BEFORE UPDATE ON {tbl} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )

    op.execute(
        """
        CREATE FUNCTION trg_observers_limit() RETURNS trigger AS $$
        BEGIN
          IF (SELECT count(*) FROM task_observers WHERE task_id = NEW.task_id) > 5 THEN
             RAISE EXCEPTION 'OBSERVERS_LIMIT_EXCEEDED: max 5 observers per task';
          END IF;
          RETURN NEW;
        END $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER observers_limit
          AFTER INSERT ON task_observers
          DEFERRABLE INITIALLY IMMEDIATE
          FOR EACH ROW EXECUTE FUNCTION trg_observers_limit()
        """
    )

    # --- 5. Сид счётчика сквозного номера ---
    op.execute("INSERT INTO counters(name, value) VALUES ('task_no', 0)")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS observers_limit ON task_observers")
    op.execute("DROP FUNCTION IF EXISTS trg_observers_limit()")
    for tbl in ("tasks", "users", "email_registry", "task_reports"):
        op.execute(f"DROP TRIGGER IF EXISTS {tbl}_touch ON {tbl}")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    for tbl in (
        "counters",
        "refresh_tokens",
        "password_reset_tokens",
        "notification_log",
        "report_attachments",
        "task_reports",
        "task_attachments",
        "task_observers",
        "tasks",
        "users",
        "email_registry",
        "projects",
    ):
        op.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")

    op.execute("DROP TYPE IF EXISTS attach_kind")
    op.execute("DROP TYPE IF EXISTS due_mode")
    op.execute("DROP TYPE IF EXISTS task_status")
    op.execute("DROP EXTENSION IF EXISTS citext")
