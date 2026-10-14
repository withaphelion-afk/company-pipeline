"""APScheduler inside the worker: re-reads the schedules table every RELOAD_SECONDS, so edits apply live."""
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.db import SessionLocal
from app.jobs.queue import enqueue
from app.jobs.runner import create_job
from app.models import Schedule, now
from app.services.control import dry_run_default, kill_switch_on
from app.services.cron import next_run, validate_cron

RELOAD_SECONDS = 30


def fire(stage: str) -> int | None:
    with SessionLocal() as s:
        if kill_switch_on(s):
            return None
        dry = dry_run_default(s)
        row = s.scalar(select(Schedule).where(Schedule.stage == stage))
        if row:
            row.last_run_at = now()
            s.commit()
    job_id = create_job(stage, None, None, dry)
    enqueue(job_id)
    return job_id


def sync(scheduler: BackgroundScheduler) -> None:
    with SessionLocal() as s:
        rows = {r.stage: r for r in s.scalars(select(Schedule))}
        wanted = {st for st, r in rows.items() if r.enabled}
        for job in scheduler.get_jobs():
            if job.id.startswith("stage:") and job.id[6:] not in wanted:
                job.remove()
        for st in wanted:
            r = rows[st]
            existing = scheduler.get_job(f"stage:{st}")
            if existing is None or getattr(existing, "_cron", None) != r.cron_expr:
                scheduler.add_job(fire, validate_cron(r.cron_expr), args=[st], id=f"stage:{st}", replace_existing=True)
                scheduler.get_job(f"stage:{st}")._cron = r.cron_expr  # type: ignore[union-attr]
            r.next_run_at = next_run(r.cron_expr)
        s.commit()


def start() -> BackgroundScheduler:
    sch = BackgroundScheduler(timezone="UTC")
    sch.add_job(sync, "interval", seconds=RELOAD_SECONDS, args=[sch], id="reload")
    sch.start()
    sync(sch)
    return sch
