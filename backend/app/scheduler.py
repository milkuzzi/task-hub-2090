"""Сборка планировщика APScheduler — общая для отдельного воркера и
in-process режима (§13.4.6).

Две независимые джобы: частый проход флага «Просрочена» и суточная рассылка.
Идемпотентность живёт в notification_log, не в состоянии планировщика, поэтому
запуск в одном экземпляре безопасен в обоих режимах.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.clock import ORG_TZ
from app.core.config import settings
from app.db.session import SessionFactory
from app.services import notification_service

log = logging.getLogger("scheduler")

# Heartbeat-файл: планировщик «отмечается» на каждом проходе sweep, а
# docker healthcheck воркера проверяет свежесть файла. Так Docker узнаёт, что
# планировщик действительно жив, а не просто процесс висит (§13.4.6).
HEARTBEAT_FILE = Path(os.environ.get("SCHEDULER_HEARTBEAT_FILE", "/tmp/scheduler-heartbeat"))


def _touch_heartbeat() -> None:
    try:
        HEARTBEAT_FILE.write_text(str(int(time.time())))
    except OSError as exc:  # не валим прогон из-за heartbeat
        log.warning("не удалось обновить heartbeat: %s", exc)


async def _sweep_job() -> None:
    _touch_heartbeat()
    async with SessionFactory() as db:
        changed = await notification_service.overdue_sweep(db)
        if changed:
            log.info("overdue_sweep: помечено просроченных: %s", changed)


async def _daily_job() -> None:
    async with SessionFactory() as db:
        await notification_service.daily_run(db)
        log.info("daily_run: рассылка выполнена")


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=ORG_TZ)
    scheduler.add_job(
        _sweep_job,
        IntervalTrigger(minutes=settings.overdue_sweep_minutes),
        id="overdue_sweep",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=settings.notify_hour, minute=settings.notify_minute, timezone=ORG_TZ),
        id="daily_run",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    return scheduler
