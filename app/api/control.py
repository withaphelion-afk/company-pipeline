import asyncio
import json
import shutil
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import control_auth
from app.core.config import get_settings
from app.core.db import SessionLocal, get_session
from app.jobs import threaded
from app.jobs.queue import enqueue, queue_depth
from app.jobs.runner import create_job
from app.models import JobLog, JobRun, Schedule, SourceSetting, Suppression, now
from app.services import control as ctl
from app.services.cron import validate_cron
from app.sources import RECOMMENDED, REGISTRY, STARTER_FILTERS
from app.sources.base import DEFAULT_SEARCH
from app.stages import STAGES

router = APIRouter(prefix="/control", dependencies=[Depends(control_auth)])
TERMINAL = {"succeeded", "failed", "cancelled"}


def job_out(j: JobRun) -> dict[str, Any]:
    return {"id": j.id, "stage": j.stage, "source": j.source, "status": j.status, "started_at": j.started_at,
            "finished_at": j.finished_at, "dry_run": j.dry_run, "error": j.error, "stats": j.stats,
            "progress": (j.stats or {}).get("progress"), "created_at": j.created_at}


def _workers() -> int | None:
    if get_settings().QUEUE_MODE == "thread":
        return 1 if threaded.alive() else 0
    try:
        from rq import Worker

        from app.jobs.queue import get_redis

        return len(Worker.all(connection=get_redis()))
    except Exception:
        return None


@router.get("/status")
def status(s: Session = Depends(get_session)) -> dict[str, Any]:
    last = {}
    for stage in STAGES:
        j = s.scalar(select(JobRun).where(JobRun.stage == stage).order_by(JobRun.id.desc()))
        last[stage] = job_out(j) if j else None
    depth = queue_depth()
    return {"workers_online": _workers(), "queue_depth": depth if depth is not None else
            s.scalar(select(func.count()).select_from(JobRun).where(JobRun.status == "queued")),
            "kill_switch": ctl.kill_switch_on(s), "last_runs": last, "stages": list(STAGES),
            "running": s.scalar(select(func.count()).select_from(JobRun).where(JobRun.status == "running"))}


class JobIn(BaseModel):
    stage: str
    source: str | None = None
    limit: int | None = Field(None, ge=1)
    dry_run: bool
    from_cache: bool = False


def _new_job(s: Session, b: JobIn) -> dict[str, Any]:
    if ctl.kill_switch_on(s):
        raise HTTPException(423, "kill switch is on; release it to queue jobs")
    if b.stage not in STAGES:
        raise HTTPException(422, f"unknown stage {b.stage}")
    if b.source and b.source not in REGISTRY:
        raise HTTPException(422, f"unknown source {b.source}")
    if b.source and REGISTRY[b.source].is_stub:
        raise HTTPException(422, f"{b.source} is a stub and cannot run")
    job_id = create_job(b.stage, b.source, b.limit, b.dry_run, b.from_cache)
    try:
        enqueue(job_id)
    except Exception as e:
        j = s.get(JobRun, job_id)
        assert j is not None
        j.status, j.error, j.finished_at = "failed", f"queue unavailable: {e}", now()
        s.commit()
        raise HTTPException(503, "queue unavailable (is Redis running?)") from e
    return {"id": job_id}


@router.post("/jobs", status_code=201)
def post_job(b: JobIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    return _new_job(s, b)


@router.post("/stages/{stage}", status_code=201)
def post_stage(stage: str, dry_run: bool | None = None, s: Session = Depends(get_session)) -> dict[str, Any]:
    return _new_job(s, JobIn(stage=stage, dry_run=ctl.dry_run_default(s) if dry_run is None else dry_run))


@router.get("/jobs")
def list_jobs(status: str | None = None, stage: str | None = None, since: datetime | None = None,
              page: int = 1, page_size: int = Query(25, le=200), s: Session = Depends(get_session)) -> dict[str, Any]:
    q = select(JobRun)
    if status:
        q = q.where(JobRun.status.in_(status.split(",")))
    if stage:
        q = q.where(JobRun.stage == stage)
    if since:
        q = q.where(JobRun.created_at >= since)
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = s.scalars(q.order_by(JobRun.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return {"total": total, "items": [job_out(j) for j in rows]}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, s: Session = Depends(get_session)) -> dict[str, Any]:
    j = s.get(JobRun, job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    logs = s.scalars(select(JobLog).where(JobLog.job_run_id == job_id).order_by(JobLog.id).limit(1000))
    return {**job_out(j), "logs": [{"id": x.id, "level": x.level, "message": x.message, "created_at": x.created_at} for x in logs]}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, s: Session = Depends(get_session)) -> dict[str, Any]:
    j = s.get(JobRun, job_id)
    if j is None:
        raise HTTPException(404, "job not found")
    if j.status in TERMINAL:
        raise HTTPException(409, f"job already {j.status}")
    if j.status == "queued":
        j.status, j.finished_at = "cancelled", now()
        s.commit()
    else:
        ctl.request_cancel(s, job_id)
    return {"id": job_id, "cancel_requested": True}


@router.get("/jobs/{job_id}/logs/stream")
async def stream_logs(job_id: int) -> StreamingResponse:
    with SessionLocal() as s:
        if s.get(JobRun, job_id) is None:
            raise HTTPException(404, "job not found")

    async def gen() -> Any:
        last = 0
        while True:
            with SessionLocal() as s:
                rows = list(s.scalars(select(JobLog).where(JobLog.job_run_id == job_id, JobLog.id > last).order_by(JobLog.id)))
                st = s.get(JobRun, job_id)
                done = st is not None and st.status in TERMINAL
            for r in rows:
                last = r.id
                if r.message.startswith("progress "):
                    yield f"event: progress\ndata: {r.message[9:]}\n\n"
                else:
                    yield f"event: log\ndata: {json.dumps({'level': r.level, 'message': r.message, 'at': r.created_at.isoformat()})}\n\n"
            if done and not rows:
                yield f"event: end\ndata: {json.dumps({'status': st.status if st else None})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# --- schedules ---------------------------------------------------------
class ScheduleIn(BaseModel):
    cron_expr: str | None = None
    enabled: bool | None = None


def schedule_out(r: Schedule) -> dict[str, Any]:
    return {"id": r.id, "stage": r.stage, "cron_expr": r.cron_expr, "enabled": r.enabled,
            "last_run_at": r.last_run_at, "next_run_at": r.next_run_at}


@router.get("/schedules")
def list_schedules(s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    existing = {r.stage for r in s.scalars(select(Schedule))}
    for st in STAGES:  # one row per stage, disabled by default
        if st not in existing:
            s.add(Schedule(stage=st, cron_expr="0 6 * * *", enabled=False))
    s.commit()
    return [schedule_out(r) for r in s.scalars(select(Schedule).order_by(Schedule.id))]


@router.put("/schedules/{sid}")
def put_schedule(sid: int, b: ScheduleIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    r = s.get(Schedule, sid)
    if r is None:
        raise HTTPException(404, "schedule not found")
    if b.cron_expr is not None:
        try:
            validate_cron(b.cron_expr)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        r.cron_expr = b.cron_expr
    if b.enabled is not None:
        r.enabled = b.enabled
    s.commit()
    return schedule_out(r)


# --- search + one-click pipeline -------------------------------------------
class SearchIn(BaseModel):
    roles: list[str] = Field(min_length=1)
    remote_only: bool = True
    goals: list[str] = Field(default_factory=lambda: ["hire", "invest", "advise"])


@router.get("/search")
def get_search(s: Session = Depends(get_session)) -> dict[str, Any]:
    return {**DEFAULT_SEARCH, **(ctl.get_setting(s, "search") or {})}


@router.put("/search")
def put_search(b: SearchIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    bad = set(b.goals) - {"hire", "invest", "advise"}
    if bad:
        raise HTTPException(422, f"unknown goals {sorted(bad)}")
    value = {"roles": [r.strip().lower() for r in b.roles if r.strip()], "remote_only": b.remote_only, "goals": b.goals}
    ctl.set_setting(s, "search", value)
    return value


PIPELINE = [("discover", 150), ("resolve_domains", 60), ("find_contacts", 60), ("verify_email", 300),
            ("enrich", 150), ("rank", None), ("draft", 100)]


class PipelineIn(BaseModel):
    dry_run: bool
    scale: float = Field(1.0, gt=0, le=5)  # multiplies the per-stage limits


@router.post("/pipeline", status_code=201)
def run_pipeline(b: PipelineIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    """Queue every stage in order; the runner executes jobs oldest first, so they run as a chain."""
    ids = [_new_job(s, JobIn(stage=st, limit=int(lim * b.scale) if lim else None, dry_run=b.dry_run))["id"] for st, lim in PIPELINE]
    return {"ids": ids}


@router.post("/sources/enable-recommended")
def enable_recommended(s: Session = Depends(get_session)) -> dict[str, Any]:
    for name in RECOMMENDED:
        r = s.scalar(select(SourceSetting).where(SourceSetting.source_name == name))
        if r is None:
            r = SourceSetting(source_name=name, rate_limit_seconds=1.0, query_filters={})
            s.add(r)
        if not r.query_filters and name in STARTER_FILTERS:
            r.query_filters = STARTER_FILTERS[name]
        r.enabled = True
    s.commit()
    return {"enabled": RECOMMENDED}


# --- sources -----------------------------------------------------------
class SourceIn(BaseModel):
    enabled: bool | None = None
    rate_limit_seconds: float | None = Field(None, ge=1)
    query_filters: dict[str, Any] | None = None


def raw_dir(name: str | None = None) -> Any:
    root = get_settings().DATA_DIR / "raw"
    return root / name if name else root


def _cached_count(name: str) -> int:
    d = raw_dir(name)
    return sum(1 for _ in d.rglob("*.json")) if d.exists() else 0


@router.get("/sources")
def list_sources(s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = {r.source_name: r for r in s.scalars(select(SourceSetting))}
    out = []
    for name, cls in REGISTRY.items():
        r = rows.get(name)
        ok = s.scalar(select(JobRun).where(JobRun.source == name, JobRun.status == "succeeded").order_by(JobRun.id.desc()))
        bad = s.scalar(select(JobRun).where(JobRun.source == name, JobRun.status == "failed").order_by(JobRun.id.desc()))
        out.append({"name": name, "is_stub": cls.is_stub, "requires_config": cls.requires_config,
                    "enabled": bool(r and r.enabled), "rate_limit_seconds": r.rate_limit_seconds if r else 2.0,
                    "query_filters": r.query_filters if r else {}, "last_success": ok.finished_at if ok else None,
                    "last_error": bad.error.strip().splitlines()[-1] if bad and bad.error else None,
                    "cached_items": _cached_count(name)})
    return out


@router.put("/sources/{name}")
def put_source(name: str, b: SourceIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    cls = REGISTRY.get(name)
    if cls is None:
        raise HTTPException(404, "unknown source")
    r = s.scalar(select(SourceSetting).where(SourceSetting.source_name == name))
    if r is None:
        r = SourceSetting(source_name=name, enabled=False, rate_limit_seconds=get_settings().DEFAULT_RATE_LIMIT_SECONDS, query_filters={})
        s.add(r)
    if b.query_filters is not None:
        r.query_filters = b.query_filters
    if b.rate_limit_seconds is not None:
        r.rate_limit_seconds = b.rate_limit_seconds
    if b.enabled:
        if cls.is_stub:
            raise HTTPException(422, f"{name} is a stub (no data source) and cannot be enabled")
        missing = cls.missing_config(r.query_filters)
        if missing:
            raise HTTPException(422, f"cannot enable {name}: missing required config {missing}")
    if b.enabled is not None:
        r.enabled = b.enabled
    s.commit()
    return {"name": name, "enabled": r.enabled, "rate_limit_seconds": r.rate_limit_seconds, "query_filters": r.query_filters}


# --- kill switch, settings, cache -----------------------------------------
class KillIn(BaseModel):
    enabled: bool


@router.post("/kill-switch")
def kill_switch(b: KillIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    ctl.set_setting(s, "kill_switch", b.enabled)
    return {"kill_switch": b.enabled}


@router.get("/settings")
def get_settings_api(s: Session = Depends(get_session)) -> dict[str, Any]:
    return {"kill_switch": ctl.kill_switch_on(s), "dry_run_default": ctl.dry_run_default(s),
            "daily_send_cap": ctl.daily_send_cap(s), "suppression_count": s.scalar(select(func.count()).select_from(Suppression)),
            "smtp_probe_enabled": get_settings().SMTP_PROBE_ENABLED}


@router.put("/settings")
def put_settings(body: dict[str, Any], s: Session = Depends(get_session)) -> dict[str, Any]:
    bad = set(body) - ctl.ALLOWED_SETTINGS
    if bad:
        raise HTTPException(422, f"settings not allowed: {sorted(bad)}")
    if "dry_run_default" in body and not isinstance(body["dry_run_default"], bool):
        raise HTTPException(422, "dry_run_default must be boolean")
    if "daily_send_cap" in body and (not isinstance(body["daily_send_cap"], int) or body["daily_send_cap"] < 0):
        raise HTTPException(422, "daily_send_cap must be a non-negative integer")
    for k, v in body.items():
        ctl.set_setting(s, k, v)
    return get_settings_api(s)


@router.get("/cache")
def cache_usage() -> list[dict[str, Any]]:
    root = raw_dir()
    out = []
    for d in sorted(root.iterdir()) if root.exists() else []:
        if d.is_dir():
            files = [f for f in d.rglob("*") if f.is_file()]
            out.append({"source": d.name, "files": len(files), "bytes": sum(f.stat().st_size for f in files)})
    return out


class CacheClear(BaseModel):
    confirm: bool = False


@router.delete("/cache")
def clear_cache(body: CacheClear, source: str | None = None, older_than_days: int | None = Query(None, ge=0)) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(400, "confirm=true required")
    if source and ("/" in source or "\\" in source or ".." in source):
        raise HTTPException(422, "invalid source")
    root = raw_dir()
    sources = [root / source] if source else (list(root.iterdir()) if root.exists() else [])
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days) if older_than_days is not None else None
    removed = 0
    for src in sources:
        for day in list(src.iterdir()) if src.is_dir() else []:
            try:
                dt = datetime.strptime(day.name, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                continue
            if day.is_dir() and (cutoff is None or dt < cutoff):
                removed += sum(1 for f in day.iterdir() if f.is_file())
                shutil.rmtree(day, ignore_errors=True)
    return {"removed_files": removed}
