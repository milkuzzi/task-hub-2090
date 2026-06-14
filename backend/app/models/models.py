"""Реляционная модель PostgreSQL (§13.2).

UUID-первичные ключи у сущностей, попадающих в URL (`users`, `email_registry`,
`tasks`) — непредсказуемые идентификаторы (§13.5.1). `task_no` (сквозной номер) и
`code6` (6-значный поисковый код) — отдельные человекочитаемые поля.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import CITEXT, Base, pg_enum
from app.domain.enums import AttachKind, DueMode, TaskStatus


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated_at() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmailRegistry(Base):
    """Белый список (реестр) e-mail — ведёт администратор (§3, §13.2.4)."""

    __tablename__ = "email_registry"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_user_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # задел MAX
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class User(Base):
    """Учётная запись (пароль привязан к e-mail); tombstone-флаг (§3, §13.2.9)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    # NULL = учётная запись ещё не активирована (приглашён, пароль не задан) —
    # вход невозможен до перехода по ссылке «задайте пароль» (§3, передача админа).
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Ключ файла-аватара в сторадже вложений (UUID-имя); NULL = аватар не загружен.
    avatar_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()


class PendingAdminHandover(Base):
    """Отложенная передача администрирования (Требование 2).

    Связывает входящего (приглашённого) администратора с исходящим. Исходящий
    НЕ удаляется и НЕ демотируется немедленно: понижение в обычные пользователи
    происходит только после активации входящего (установки пароля) — иначе
    неудачное письмо/брошенное приглашение оставило бы сервис без администратора.
    """

    __tablename__ = "pending_admin_handover"
    __table_args__ = (
        Index("uq_pending_handover_incoming", "incoming_user_id", unique=True),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    incoming_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    outgoing_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()


class Project(Base):
    """ЗАДЕЛ: сущность «проект» не используется в MVP (§2/§12, §13.2.8)."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Task(Base):
    """Центральная сущность (§5, §13.2.4)."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("char_length(btrim(title)) > 0", name="ck_tasks_title_not_blank"),
        CheckConstraint("code6 BETWEEN 100000 AND 999999", name="ck_tasks_code6_range"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_no: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    code6: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_mode: Mapped[DueMode] = mapped_column(
        pg_enum(DueMode, "due_mode"), nullable=False, server_default=DueMode.DATETIME.value
    )
    due_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    status: Mapped[TaskStatus] = mapped_column(
        pg_enum(TaskStatus, "task_status"),
        nullable=False,
        server_default=TaskStatus.IN_PROGRESS.value,
    )
    is_overdue: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    overdue_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    needs_reassignment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    author_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    author: Mapped[User] = relationship("User", foreign_keys=[author_id], lazy="joined")
    assignees: Mapped[list[TaskAssignee]] = relationship(
        "TaskAssignee", cascade="all, delete-orphan", lazy="selectin"
    )
    observers: Mapped[list[TaskObserver]] = relationship(
        "TaskObserver", cascade="all, delete-orphan", lazy="selectin"
    )
    attachments: Mapped[list[TaskAttachment]] = relationship(
        "TaskAttachment", cascade="all, delete-orphan", lazy="selectin"
    )
    report: Mapped[TaskReport | None] = relationship(
        "TaskReport", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    @property
    def observer_ids(self) -> list[uuid.UUID]:
        return [o.user_id for o in self.observers]

    @property
    def assignee_ids(self) -> list[uuid.UUID]:
        return [a.user_id for a in self.assignees]


class TaskAssignee(Base):
    """Исполнители задачи (M:N, ≥1 на уровне приложения) (§2, design.md)."""

    __tablename__ = "task_assignees"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )

    user: Mapped[User] = relationship("User", lazy="joined")


class TaskObserver(Base):
    """Наблюдатели задачи (M:N, ≤5; снапшот display_name для tombstone) (§13.2.4)."""

    __tablename__ = "task_observers"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    added_at: Mapped[datetime] = _created_at()

    user: Mapped[User] = relationship("User", lazy="joined")


class TaskAttachment(Base):
    """Вложение исходной задачи (файл или ссылка) (§13.2.4)."""

    __tablename__ = "task_attachments"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'file' AND file_path IS NOT NULL AND url IS NULL) "
            "OR (kind = 'url' AND url IS NOT NULL AND file_path IS NULL)",
            name="ck_task_attach_kind",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[AttachKind] = mapped_column(pg_enum(AttachKind, "attach_kind"), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()


class TaskReport(Base):
    """Отчёт исполнителя (1:1 с задачей; пишет только исполнитель) (§13.2.4)."""

    __tablename__ = "task_reports"

    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ready_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _updated_at()

    attachments: Mapped[list[ReportAttachment]] = relationship(
        "ReportAttachment", cascade="all, delete-orphan", lazy="selectin"
    )


class ReportAttachment(Base):
    """Вложение отчёта исполнителя (§13.2.4)."""

    __tablename__ = "report_attachments"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'file' AND file_path IS NOT NULL AND url IS NULL) "
            "OR (kind = 'url' AND url IS NOT NULL AND file_path IS NULL)",
            name="ck_report_attach_kind",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("task_reports.task_id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[AttachKind] = mapped_column(pg_enum(AttachKind, "attach_kind"), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()


class TaskMessage(Base):
    """Сообщение чата задачи (§4, design.md «task_messages»).

    `author_id` RESTRICT: имя автора показываем по актуальному `display_name`
    (для tombstone-пользователя — «Пользователь удалён» на уровне отображения),
    поэтому снапшот имени не храним. Длина тела ограничивается приложением
    (`settings.max_message_len`).
    """

    __tablename__ = "task_messages"
    __table_args__ = (Index("ix_task_messages_task", "task_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    author: Mapped[User] = relationship("User", lazy="joined")


class Notification(Base):
    """On-site уведомление пользователю (§6, design.md «notifications»).

    `kind` — 'chat_message' | 'task_rework'. `task_id`/`message_id` опциональны
    (CASCADE при удалении ссылки). E-mail по этим событиям не отправляется.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_user_unread",
            "user_id",
            "is_read",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("task_messages.id", ondelete="CASCADE"), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = _created_at()


class NotificationLog(Base):
    """Журнал отправленных уведомлений — идемпотентность планировщика (§13.4.3)."""

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    due_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    email_status: Mapped[str] = mapped_column(Text, nullable=False)
    max_status: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _created_at()


class PasswordResetToken(Base):
    """Одноразовые токены сброса пароля (хранится хэш) (§13.3.4)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class RefreshToken(Base):
    """Refresh-токены сессии (хранится хэш) — мгновенный отзыв (§13.3.2)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()


class Counter(Base):
    """Таблица-счётчик для сквозного номера без дыр (§13.2.5)."""

    __tablename__ = "counters"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
