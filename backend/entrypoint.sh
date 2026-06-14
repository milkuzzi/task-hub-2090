#!/usr/bin/env bash
set -e

ROLE="${1:-api}"

case "$ROLE" in
  api)
    echo "[entrypoint] Применяю миграции (alembic upgrade head)…"
    alembic upgrade head
    if [ "${RUN_SEED}" = "true" ]; then
      echo "[entrypoint] Запускаю сид…"
      python -m app.seed || echo "[entrypoint] сид завершился с предупреждением"
    fi
    echo "[entrypoint] Старт API (uvicorn)…"
    # Доверяем X-Forwarded-* только от обратного прокси (Caddy во внутренней сети
    # Docker), а не от всех клиентов: иначе можно подделать X-Forwarded-For и обойти
    # rate limiter аутентификации. Значение настраивается через FORWARDED_ALLOW_IPS;
    # безопасный дефолт — CIDR внутренней сети Docker (НЕ '*').
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
      --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-172.16.0.0/12}"
    ;;
  worker)
    echo "[entrypoint] Старт воркера-планировщика…"
    exec python -m app.worker
    ;;
  seed)
    exec python -m app.seed
    ;;
  *)
    exec "$@"
    ;;
esac
