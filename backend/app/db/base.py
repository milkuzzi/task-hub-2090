"""Декларативная база SQLAlchemy и общие типы/хелперы.

CITEXT — собственный тип, рендерящийся в PostgreSQL `CITEXT` (регистронезависимое
сравнение e-mail, §13.2.4). Создание расширения citext — в миграции.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import types
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class CITEXT(types.UserDefinedType):
    """Регистронезависимый текст PostgreSQL (расширение citext)."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "CITEXT"


def pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """PostgreSQL ENUM, хранящий ЗНАЧЕНИЯ StrEnum (in_progress), а не имена.

    `create_type=False` — типы создаются миграцией, не моделью (мы не используем
    `create_all`/autogenerate для DDL).
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        create_type=False,
        validate_strings=True,
        values_callable=lambda e: [member.value for member in e],
    )
