"""Воркер-планировщик: отдельный контейнер из того же образа, что backend (§13.4.6).

Запускается, когда планировщик НЕ встроен в backend (SCHEDULER_IN_PROCESS=false,
режим по умолчанию). Ровно один экземпляр; идемпотентность — в notification_log.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.scheduler import build_scheduler

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("worker")


async def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    log.info(
        "worker запущен: sweep каждые %s мин, рассылка в %s (%s)",
        settings.overdue_sweep_minutes,
        settings.notify_time,
        settings.tz,
    )
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
