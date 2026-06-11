"""Единая модель ошибок и каталог кодов (§13.5.2).

Все ошибки отдаются единым телом `{"error": {"code", "message", "details"}}`.
`code` — стабильная контрактная константа (UPPER_SNAKE), по ней ветвится фронтенд;
текст можно менять без слома клиента.
"""

from __future__ import annotations

from typing import Any

# Дословная фраза отказа в доступе (§3 п.3, §2). Изменять нельзя — закреплена тестом.
NO_ACCESS_MESSAGE = "Извините, у вас нет доступа к сервису."


class AppError(Exception):
    """Базовая прикладная ошибка: несёт HTTP-статус, код и русское сообщение."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details

    def to_body(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            error["details"] = self.details
        return {"error": error}


# --- Фабрики типовых ошибок (каталог §13.5.2) ---


def bad_request(message: str = "Некорректный запрос.") -> AppError:
    return AppError(400, "BAD_REQUEST", message)


def unauthenticated(message: str = "Требуется вход в систему.") -> AppError:
    return AppError(401, "UNAUTHENTICATED", message)


def registry_access_revoked() -> AppError:
    return AppError(401, "REGISTRY_ACCESS_REVOKED", "Доступ к сервису прекращён.")


def forbidden_role() -> AppError:
    return AppError(403, "FORBIDDEN_ROLE", "Недостаточно прав для этого действия.")


def forbidden_admin() -> AppError:
    return AppError(403, "FORBIDDEN_ADMIN", "Действие доступно только администратору.")


def email_not_in_registry() -> AppError:
    # Особый случай отказа в регистрации — дословная фраза из ТЗ.
    return AppError(403, "EMAIL_NOT_IN_REGISTRY", NO_ACCESS_MESSAGE)


def task_not_found() -> AppError:
    return AppError(404, "TASK_NOT_FOUND", "Задача не найдена.")


def user_not_found() -> AppError:
    return AppError(404, "USER_NOT_FOUND", "Пользователь не найден.")


def attachment_not_found() -> AppError:
    return AppError(404, "ATTACHMENT_NOT_FOUND", "Вложение не найдено.")


def status_conflict() -> AppError:
    return AppError(409, "STATUS_CONFLICT", "Действие невозможно в текущем статусе задачи.")


def already_ready() -> AppError:
    return AppError(409, "ALREADY_READY", "Готовность уже отмечена.")


def email_already_registered() -> AppError:
    return AppError(409, "EMAIL_ALREADY_REGISTERED", "Этот e-mail уже зарегистрирован.")


def validation_error(details: list[dict[str, Any]] | None = None) -> AppError:
    return AppError(422, "VALIDATION_ERROR", "Проверьте правильность заполнения полей.", details)


def file_too_large() -> AppError:
    return AppError(413, "FILE_TOO_LARGE", "Файл превышает допустимый размер.")


def attachments_limit() -> AppError:
    return AppError(409, "ATTACHMENTS_LIMIT", "Превышено допустимое число вложений.")


def unsupported_filename() -> AppError:
    return AppError(415, "UNSUPPORTED_FILENAME", "Недопустимое имя файла.")


def rate_limited() -> AppError:
    return AppError(429, "RATE_LIMITED", "Слишком много попыток, повторите позже.")


def internal_error() -> AppError:
    return AppError(500, "INTERNAL", "Внутренняя ошибка сервиса.")
