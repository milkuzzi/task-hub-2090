"""Healthcheck воркера-планировщика для Docker.

Проверяет свежесть heartbeat-файла, который планировщик обновляет на каждом
проходе sweep. Если файл старше допустимого порога — процесс «живой», но
планировщик не работает: контейнер помечается unhealthy и перезапускается.

Порог = интервал sweep + запас. Использование:
    python -m app.healthcheck
Код возврата 0 — healthy, 1 — unhealthy.
"""

from __future__ import annotations

import sys
import time

from app.core.config import settings
from app.scheduler import HEARTBEAT_FILE


def main() -> int:
    # Запас: два интервала sweep + минута на случай долгого прогона/нагрузки.
    max_age = settings.overdue_sweep_minutes * 60 * 2 + 60
    try:
        last = int(HEARTBEAT_FILE.read_text().strip())
    except (OSError, ValueError):
        print("heartbeat недоступен", file=sys.stderr)
        return 1
    age = int(time.time()) - last
    if age > max_age:
        print(f"heartbeat устарел: {age}s > {max_age}s", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
