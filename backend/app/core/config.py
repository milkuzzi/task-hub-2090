"""Конфигурация приложения (12-factor через переменные окружения).

Все настройки читаются из окружения/`.env` через pydantic-settings, что даёт
валидацию конфига на старте: отсутствие обязательной переменной → падение
контейнера на старте, а не тихая ошибка в рантайме (см. §13.1.6 ТЗ).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Окружение ---
    app_env: str = Field(default="dev")  # dev | prod
    log_level: str = Field(default="INFO")

    # --- БД ---
    database_url: str = Field(
        default="postgresql+asyncpg://taskhub:taskhub@db:5432/taskhub",
    )

    # Размер пула соединений на процесс. backend + worker делят db.max_connections,
    # поэтому держим пул небольшим (5 + до 5 overflow = max 10 на процесс).
    db_pool_size: int = Field(default=5)
    db_max_overflow: int = Field(default=5)

    # --- JWT / секреты ---
    jwt_secret: str = Field(default=_DEV_JWT_SECRET)
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_ttl_min: int = Field(default=15)
    refresh_ttl_days: int = Field(default=14)
    password_reset_ttl_min: int = Field(default=60)

    # --- SMTP (обязательный канал) ---
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=1025)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_tls: bool = Field(default=False)
    smtp_from: str = Field(default="noreply@school2090.local")

    # --- MAX (best-effort) ---
    max_enabled: bool = Field(default=False)
    max_api_base: str = Field(default="")
    max_bot_token: str = Field(default="")
    max_blocked_ext: str = Field(default=".html,.htm,.svg")
    max_file_size_mb: int = Field(default=20)

    # --- Хранилище вложений ---
    storage_backend: str = Field(default="file")  # file | s3
    attachments_dir: str = Field(default="/data/attachments")

    # --- Лимиты загрузки ---
    max_file_size_mb_upload: int = Field(default=25, alias="MAX_FILE_SIZE_MB")
    max_files_per_task: int = Field(default=20)
    max_files_per_report: int = Field(default=10)
    max_task_total_mb: int = Field(default=200)
    max_observers: int = Field(default=5)

    # Предел суммарного/одиночного объёма вложений, инлайнящихся в одно письмо.
    # Канал e-mail читает файлы в память, поэтому на воркере с 256 МБ большие
    # вложения не инлайнятся, а заменяются ссылкой в теле (защита от OOM).
    max_email_attachment_mb: int = Field(default=10)

    # --- Таймзона и расписание ---
    tz: str = Field(default="Europe/Moscow", alias="TZ")
    notify_time: str = Field(default="09:00")  # HH:MM в таймзоне организации
    overdue_sweep_minutes: int = Field(default=10)
    # Запускать планировщик внутри backend-процесса (3 контейнера вместо 4).
    # По умолчанию false → планировщик в отдельном контейнере worker (изоляция отказов).
    scheduler_in_process: bool = Field(default=False)

    # --- Адрес / доступ ---
    base_url: str = Field(default="http://localhost:8080")
    cors_origins: str = Field(default="http://localhost:8080,http://localhost:5173")

    # --- Rate limit на auth-эндпоинты (вход, регистрация, сброс пароля) ---
    auth_rate_limit_enabled: bool = Field(default=True)

    # --- Первичный администратор ---
    admin_email: str = Field(default="")
    admin_password: str = Field(default="")
    # Секрет для консольной команды создания первичного администратора
    # (`python -m app.cli.create_admin`). Сверяется timing-safe с ADMIN_CREATION_TOKEN
    # из окружения — без него команда отказывает в создании администратора.
    admin_creation_token: str = Field(default="")

    # --- Сид ---
    run_seed: bool = Field(default=False)
    seed_registry_file: str = Field(default="")
    seed_demo: bool = Field(default=False)

    # --- Экспорт ---
    export_pdf_enabled: bool = Field(default=False)

    @property
    def notify_hour(self) -> int:
        return int(self.notify_time.split(":")[0])

    @property
    def notify_minute(self) -> int:
        parts = self.notify_time.split(":")
        return int(parts[1]) if len(parts) > 1 else 0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_blocked_ext_set(self) -> set[str]:
        return {e.strip().lower() for e in self.max_blocked_ext.split(",") if e.strip()}

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "prod"

    @model_validator(mode="after")
    def _no_insecure_defaults_in_prod(self) -> Settings:
        """Fail-fast: в проде нельзя стартовать с дефолтным JWT_SECRET (§13.1.6).

        Иначе любой, кто читал исходники, сможет подделывать access-токены.
        """
        if self.is_prod and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError(
                "APP_ENV=prod, но JWT_SECRET не задан (остался небезопасный дефолт). "
                "Задайте в .env длинную случайную строку, например: "
                "python3 -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
