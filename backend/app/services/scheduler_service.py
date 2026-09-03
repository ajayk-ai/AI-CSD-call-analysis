"""In-process daily auto-analysis schedule.

One persisted row (`scheduler_config`) drives one APScheduler job
("daily_pipeline_run"). This only runs while the backend process is up —
there is no OS-level cron fallback — which is the tradeoff for making the
schedule fully controllable from the Admin tab without touching the host.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SchedulerConfig
from app.db.session import SessionLocal
from app.pipeline.ingest_pipeline import run_pipeline

logger = logging.getLogger(__name__)

_JOB_ID = "daily_pipeline_run"
_scheduler: BackgroundScheduler | None = None


def get_config(db: Session) -> SchedulerConfig:
    """Fetches the single settings row, creating a disabled default on first
    access. Not a fixed id — the table only ever holds one row."""
    config = db.execute(select(SchedulerConfig).limit(1)).scalar_one_or_none()
    if config is None:
        config = SchedulerConfig()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def update_config(
    db: Session,
    *,
    enabled: bool,
    run_hour: int,
    run_minute: int,
    run_limit: int | None,
) -> SchedulerConfig:
    config = get_config(db)
    config.enabled = enabled
    config.run_hour = run_hour
    config.run_minute = run_minute
    config.run_limit = run_limit
    db.commit()
    db.refresh(config)
    _reschedule(config)
    return config


def _run_scheduled_job() -> None:
    """Runs on APScheduler's own thread, so it opens and closes its own
    session rather than relying on a request-scoped one. Failures are caught
    and recorded on the row instead of propagating — an uncaught exception
    here would silently kill future firings of the job."""
    db = SessionLocal()
    try:
        config = get_config(db)
        summary = run_pipeline(db, limit=config.run_limit)
        config.last_run_at = datetime.now(timezone.utc)
        config.last_run_status = "success"
        config.last_run_summary = (
            f"Analyzed {summary.newly_processed - summary.skipped_by_prescreen}, "
            f"skipped {summary.skipped_by_prescreen}, failed {summary.failed}, "
            f"{summary.remaining_pending} still queued."
        )
        db.commit()
        logger.info("Scheduled pipeline run complete: %s", config.last_run_summary)
    except Exception as exc:  # noqa: BLE001 - the failure IS the result here
        logger.exception("Scheduled pipeline run failed")
        db.rollback()
        config = get_config(db)
        config.last_run_at = datetime.now(timezone.utc)
        config.last_run_status = "error"
        config.last_run_summary = f"{type(exc).__name__}: {exc}"
        db.commit()
    finally:
        db.close()


def _reschedule(config: SchedulerConfig) -> None:
    if _scheduler is None:
        return
    if _scheduler.get_job(_JOB_ID) is not None:
        _scheduler.remove_job(_JOB_ID)
    if config.enabled:
        _scheduler.add_job(
            _run_scheduled_job,
            trigger=CronTrigger(hour=config.run_hour, minute=config.run_minute),
            id=_JOB_ID,
        )
        logger.info(
            "Daily pipeline run scheduled for %02d:%02d", config.run_hour, config.run_minute
        )


def init_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    db = SessionLocal()
    try:
        config = get_config(db)
    finally:
        db.close()
    _scheduler.start()
    _reschedule(config)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
