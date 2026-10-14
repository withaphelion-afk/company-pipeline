import argparse
import sys

from sqlalchemy import delete

from app.core.db import SessionLocal
from app.core.logging import setup_logging
from app.jobs.runner import create_job, run_job
from app.models import Draft, Person
from app.services.control import dry_run_default
from app.stages import STAGES


def cmd_run(a: argparse.Namespace) -> int:
    with SessionLocal() as s:
        dry = a.dry_run if a.dry_run is not None else dry_run_default(s)
    stages = list(STAGES) if a.stage == "all" else [a.stage]
    for st in stages:
        job_id = create_job(st, a.source, a.limit, dry, a.from_cache)
        status = run_job(job_id)
        print(f"{st}: job {job_id} {status}{' (dry run)' if dry else ''}")
        if status != "succeeded":
            return 1
    return 0


def cmd_purge(a: argparse.Namespace) -> int:
    with SessionLocal() as s:
        p = s.get(Person, a.person)
        if p is None:
            print(f"person {a.person} not found")
            return 1
        s.execute(delete(Draft).where(Draft.person_id == p.id))
        s.delete(p)  # emails cascade
        s.commit()
        print(f"purged person {a.person}, their emails and drafts")
    return 0


def cmd_worker(_: argparse.Namespace) -> int:
    from rq import Queue, SimpleWorker

    from app.jobs import scheduler
    from app.jobs.queue import QUEUE_NAME, get_redis

    scheduler.start()
    conn = get_redis()
    # SimpleWorker: no fork(), so it also runs on Windows. Prefer the standard rq Worker on Linux/macOS.
    SimpleWorker([Queue(QUEUE_NAME, connection=conn)], connection=conn).work()
    return 0


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    ap = argparse.ArgumentParser(prog="python -m pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a stage (or all) in-process")
    r.add_argument("--stage", required=True, choices=["all", *STAGES])
    r.add_argument("--source")
    r.add_argument("--limit", type=int)
    r.add_argument("--from-cache", action="store_true")
    r.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    r.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    r.set_defaults(fn=cmd_run)
    pg = sub.add_parser("purge", help="delete a person with all emails and drafts")
    pg.add_argument("--person", type=int, required=True)
    pg.set_defaults(fn=cmd_purge)
    w = sub.add_parser("worker", help="RQ worker + APScheduler")
    w.set_defaults(fn=cmd_worker)
    sys.exit(ns.fn(ns) if (ns := ap.parse_args(argv)) else 0)
