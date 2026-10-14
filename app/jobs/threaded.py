"""In-process runner for single-container hosting: one thread runs queued jobs in order, APScheduler fires schedules.
No Redis needed; job state lives in job_runs, so a restart simply resumes with whatever is still queued."""
import logging
import threading

from sqlalchemy import select

from app.core.db import SessionLocal
from app.jobs import scheduler
from app.jobs.runner import run_job
from app.models import JobRun, now

log = logging.getLogger("pipeline.worker")
POLL_SECONDS = 2.0
_stop = threading.Event()
_thread: threading.Thread | None = None
_sched = None


def _next_job_id() -> int | None:
    with SessionLocal() as s:
        return s.scalar(select(JobRun.id).where(JobRun.status == "queued").order_by(JobRun.id).limit(1))


def _recover() -> None:
    """Jobs left 'running' by a killed process can never finish; mark them failed."""
    with SessionLocal() as s:
        for j in s.scalars(select(JobRun).where(JobRun.status == "running")):
            j.status, j.error, j.finished_at = "failed", "process restarted while running", now()
        s.commit()


def _loop() -> None:
    while not _stop.is_set():
        try:
            jid = _next_job_id()
            if jid is not None:
                run_job(jid)
                continue
        except Exception:
            log.exception("worker loop error")
        _stop.wait(POLL_SECONDS)


def start() -> None:
    global _thread, _sched
    if alive():
        return
    _stop.clear()
    _recover()
    _sched = scheduler.start()
    _thread = threading.Thread(target=_loop, name="job-runner", daemon=True)
    _thread.start()


def stop() -> None:
    global _thread, _sched
    _stop.set()
    if _sched is not None:
        _sched.shutdown(wait=False)
        _sched = None
    _thread = None


def alive() -> bool:
    return _thread is not None and _thread.is_alive()
