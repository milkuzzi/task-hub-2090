#!/usr/bin/env bash
# Бэкап БД и вложений для self-host на одном VPS.
# Запускать с хоста из корня проекта (где docker-compose.yml).
#
# Разовый запуск:   ./infra/backup.sh
# По расписанию (crontab -e), каждый день в 03:30:
#   30 3 * * * cd /opt/task-hub-2090 && ./infra/backup.sh >> /var/log/taskhub-backup.log 2>&1
#
# Восстановление БД:
#   gunzip -c backups/db-YYYYmmdd-HHMMSS.sql.gz | docker compose exec -T db psql -U taskhub -d taskhub
# Восстановление вложений:
#   docker compose exec -T backend sh -c 'cd /data/attachments && tar xzf -' < backups/attachments-YYYYmmdd-HHMMSS.tar.gz

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP="${KEEP:-14}"            # сколько последних копий хранить
ATTACH_DIR="${ATTACHMENTS_DIR:-/data/attachments}"
STAMP="$(date +%Y%m%d-%H%M%S)"

# Подхватываем POSTGRES_* из .env, если есть
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
PG_USER="${POSTGRES_USER:-taskhub}"
PG_DB="${POSTGRES_DB:-taskhub}"

mkdir -p "$BACKUP_DIR"

# Пишем во временные файлы и переименовываем только при успехе — чтобы
# прерванный бэкап не оставил «битый» файл, который ротация сочтёт валидным.
DB_TMP="$BACKUP_DIR/.db-$STAMP.sql.gz.part"
ATTACH_TMP="$BACKUP_DIR/.attachments-$STAMP.tar.gz.part"
cleanup() { rm -f "$DB_TMP" "$ATTACH_TMP"; }
trap cleanup EXIT

echo "[backup] Дамп БД…"
docker compose exec -T db pg_dump -U "$PG_USER" "$PG_DB" | gzip > "$DB_TMP"
# Проверка целостности gzip — если дамп оборвался, не публикуем его.
gzip -t "$DB_TMP"
mv "$DB_TMP" "$BACKUP_DIR/db-$STAMP.sql.gz"

echo "[backup] Архив вложений…"
docker compose exec -T backend tar czf - -C "$ATTACH_DIR" . > "$ATTACH_TMP"
gzip -t "$ATTACH_TMP"
mv "$ATTACH_TMP" "$BACKUP_DIR/attachments-$STAMP.tar.gz"

trap - EXIT

echo "[backup] Ротация (храним последние $KEEP)…"
ls -1t "$BACKUP_DIR"/db-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
ls -1t "$BACKUP_DIR"/attachments-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "[backup] Готово: $STAMP → $BACKUP_DIR"
