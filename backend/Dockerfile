# --- Стадия сборки: компилируем зависимости в venv, build-tools не попадают в финал ---
FROM python:3.12-slim AS build

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости только для сборки (argon2-cffi и т.п.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Изолированный venv — переносим целиком в рантайм-образ.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# --- Рантайм: чистый slim без компиляторов, запуск от непривилегированного пользователя ---
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    SCHEDULER_HEARTBEAT_FILE=/tmp/scheduler-heartbeat

WORKDIR /app

# libpq нужна в рантайме для asyncpg/psycopg драйверов.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=build /opt/venv /opt/venv
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY entrypoint.sh ./entrypoint.sh
# Точка монтирования тома вложений: создаём заранее с владельцем appuser, чтобы
# Docker унаследовал права при инициализации пустого named volume (запись от non-root).
RUN chmod +x entrypoint.sh \
    && mkdir -p /data/attachments \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
CMD ["api"]
