"""Job lifecycle: create, run (kill switch / cancel / dry-run aware), finish."""
import traceback
from typing import Any

from app.core.db import SessionLocal
from app.models import JobLog, JobRun, now
from app.services.control import Cancelled, KillSwitchOn, clear_cancel, kill_switch_on
from app.stages import STAGES
from app.stages.base import StageContext


def create_job(stage: str, source: str | None, limit: int | None, dry_run: bool, from_cache: bool = False) -> int:
    with SessionLocal() as s:
        job = JobRun(stage=stage, source=source, status="queued", dry_run=dry_run,
                     stats={"params": {"limit": limit, "from_cache": from_cache}})
        s.add(job)
        s.commit()
        return job.id


def _finish(job_id: int, status: str, error: str | None, stats: dict[str, Any]) -> None:
    with SessionLocal() as s:
        job = s.get(JobRun, job_id)
        assert job is not None
        job.status, job.error, job.finished_at = status, error, now()
        job.stats = {**(job.stats or {}), **stats}
        s.commit()
        clear_cancel(s, job_id)


def run_job(job_id: int) -> str:
    """Execute a queued job and return its final status."""
    with SessionLocal() as ctl:
        job = ctl.get(JobRun, job_id)
        if job is None or job.status != "queued":
            return job.status if job else "missing"
        if kill_switch_on(ctl):  # workers do not pick up queued jobs while the switch is on
            ctl.add(JobLog(job_run_id=job_id, level="warn", message="kill switch enabled; job not started"))
            ctl.commit()
            _finish(job_id, "cancelled", "kill switch enabled", {})
            return "cancelled"
        job.status, job.started_at = "running", now()
        ctl.commit()
        stage, source, dry_run = job.stage, job.source, job.dry_run
        params = (job.stats or {}).get("params", {})
    session = SessionLocal()
    ctx = StageContext(session, job_id, dry_run, source, params.get("limit"), bool(params.get("from_cache")))
    status, error = "succeeded", None
    try:
        ctx.check()
        STAGES[stage](ctx)
        (session.rollback if dry_run else session.commit)()
    except Cancelled:
        status = "cancelled"
        (session.rollback if dry_run else session.commit)()  # keep completed items
    except KillSwitchOn:
        status, error = "cancelled", "kill switch enabled"
        (session.rollback if dry_run else session.commit)()
    except Exception:
        status, error = "failed", traceback.format_exc()
        session.rollback()
    finally:
        counts = dict(ctx.counts)
        stats: dict[str, Any] = {"counts": counts, "progress": ctx.progress_state, "warnings": ctx.warnings}
        if dry_run:
            stats["dry_run_report"] = {"would_change": counts}  # nothing was written
        session.close()
        ctx.flush_logs()
        ctx.close()
    ctx_log_final(job_id, status, error)
    _finish(job_id, status, error, stats)
    return status


def ctx_log_final(job_id: int, status: str, error: str | None) -> None:
    with SessionLocal() as s:
        s.add(JobLog(job_run_id=job_id, level="error" if status == "failed" else "info",
                     message=f"job {status}" + (f": {error.splitlines()[-1]}" if error else "")))
        s.commit()
