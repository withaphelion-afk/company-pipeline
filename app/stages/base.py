"""Shared stage plumbing: logging, progress, kill-switch/cancel checks, source construction."""
import json
from collections import Counter

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_engine
from app.models import JobLog, SourceSetting, Suppression
from app.services.control import Cancelled, KillSwitchOn, cancel_requested, kill_switch_on
from app.services.http_client import HttpClient
from app.sources import REGISTRY, Source

# Test hooks: inject an httpx transport and force a rate limit of 0 without touching production code paths.
HTTP_TRANSPORT: httpx.BaseTransport | None = None
RATE_OVERRIDE: float | None = None


class StageContext:
    def __init__(
        self,
        session: Session,
        job_id: int,
        dry_run: bool,
        source: str | None = None,
        limit: int | None = None,
        from_cache: bool = False,
    ):
        self.session, self.job_id, self.dry_run = session, job_id, dry_run
        self.source_name, self.limit, self.from_cache = source, limit, from_cache
        self.counts: Counter[str] = Counter()
        self.progress_state = {"processed": 0, "total": 0, "errors": 0}
        self.warnings: list[str] = []
        self._ctl = SessionLocal()  # separate connection: logs/flags are visible to other processes immediately
        self._sources: dict[str, Source] = {}
        # SQLite (tests only) allows one writer, so logs wait for the stage transaction to end; Postgres logs live.
        self._buffer = get_engine().dialect.name == "sqlite"
        self._pending: list[tuple[str, str]] = []

    def close(self) -> None:
        self._ctl.close()

    # --- reporting ---------------------------------------------------
    def log(self, level: str, message: str) -> None:
        if level == "warn":
            self.warnings.append(message)
        if self._buffer:
            self._pending.append((level, message))
            return
        self._ctl.add(JobLog(job_run_id=self.job_id, level=level, message=message))
        self._ctl.commit()

    def flush_logs(self) -> None:
        for level, message in self._pending:
            self._ctl.add(JobLog(job_run_id=self.job_id, level=level, message=message))
        self._pending = []
        self._ctl.commit()

    def progress(self, processed: int, total: int, errors: int = 0) -> None:
        self.progress_state = {"processed": processed, "total": total, "errors": errors}
        self.log("info", "progress " + json.dumps(self.progress_state))

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] += n

    # --- control -----------------------------------------------------
    def check(self) -> None:
        """Call between items: stops within one item of a cancel request or kill switch."""
        self._ctl.expire_all()
        if kill_switch_on(self._ctl):
            raise KillSwitchOn()
        if cancel_requested(self._ctl, self.job_id):
            raise Cancelled()

    # --- sources / http ----------------------------------------------
    def client(self, name: str, rate: float | None = None) -> HttpClient:
        return HttpClient(
            name,
            rate_limit=RATE_OVERRIDE if RATE_OVERRIDE is not None else rate,
            from_cache=self.from_cache,
            transport=HTTP_TRANSPORT,
        )

    def setting(self, name: str) -> SourceSetting | None:
        return self._ctl.scalar(select(SourceSetting).where(SourceSetting.source_name == name))

    def source(self, name: str) -> Source:
        if name not in self._sources:
            cls = REGISTRY[name]
            row = self.setting(name)
            self._sources[name] = cls(self.client(name, row.rate_limit_seconds if row else None), row.query_filters if row else {})
        return self._sources[name]

    def enabled_sources(self, names: list[str]) -> list[str]:
        if self.source_name:
            return [self.source_name] if self.source_name in names else []
        out = []
        for n in names:
            row = self.setting(n)
            if row and row.enabled and not REGISTRY[n].is_stub:
                out.append(n)
        return out

    def suppressed(self) -> "SuppressionSet":
        return SuppressionSet(set(self.session.scalars(select(Suppression.email_or_domain))))


class SuppressionSet:
    def __init__(self, items: set[str]):
        self.items = {i.lower() for i in items}

    def __contains__(self, address: str) -> bool:
        a = address.lower()
        return a in self.items or a.rsplit("@", 1)[-1] in self.items
