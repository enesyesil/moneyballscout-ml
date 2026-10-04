"""Scheduler process: the only service that calls API-Football and writes to the database.

  daily  (SYNC_CRON_HOUR UTC)  sync -> link -> train
  weekly (Monday 03:00 UTC)    Transfermarkt snapshot -> link
On start it runs one daily cycle so a fresh deploy fills itself.
"""

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.cli import daily
from app.core.config import get_settings
from app.core.db import advisory_lock, session_scope
from app.ingest import entity_resolution, transfermarkt

log = logging.getLogger("worker")


def daily_job() -> None:
    with advisory_lock() as acquired:
        if not acquired:
            log.warning("pipeline already running; skipping")
            return
        with session_scope() as s:
            daily(s)


def weekly_job() -> None:
    with advisory_lock() as acquired:
        if not acquired:
            return
        with session_scope() as s:
            log.info("transfermarkt: %s", transfermarkt.refresh(s))
            s.commit()
            log.info("linking: %s", entity_resolution.resolve(s))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    s = get_settings()
    if not s.api_football_key:
        log.error("API_FOOTBALL_KEY is not set; the worker will only retrain on stored data")
    sched = BlockingScheduler(timezone="UTC")
    sched.add_job(daily_job, CronTrigger(hour=s.sync_cron_hour, minute=0), id="daily", max_instances=1, coalesce=True)
    sched.add_job(weekly_job, CronTrigger(day_of_week="mon", hour=3, minute=0), id="weekly", max_instances=1, coalesce=True)
    if os.getenv("RUN_ON_START", "1") == "1":
        try:
            with session_scope() as sess:
                from app.models import TMPlayer

                has_tm = sess.query(TMPlayer.id).first() is not None
            if not has_tm:
                weekly_job()
        except Exception:  # noqa: BLE001
            log.exception("initial transfermarkt load failed")
        try:
            daily_job()
        except Exception:  # noqa: BLE001
            log.exception("initial daily run failed")
    log.info("scheduler started: daily at %02d:00 UTC, transfermarkt weekly", s.sync_cron_hour)
    sched.start()


if __name__ == "__main__":
    main()
