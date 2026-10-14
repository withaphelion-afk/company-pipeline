from redis import Redis
from rq import Queue

from app.core.config import get_settings

QUEUE_NAME = "pipeline"


def get_redis() -> Redis:
    return Redis.from_url(get_settings().REDIS_URL, socket_connect_timeout=2)


def enqueue(job_id: int) -> None:
    """Push to RQ. QUEUE_MODE=none only leaves the job row queued (used by tests)."""
    if get_settings().QUEUE_MODE == "none":
        return
    Queue(QUEUE_NAME, connection=get_redis()).enqueue("app.jobs.runner.run_job", job_id, job_timeout=3600)


def queue_depth() -> int | None:
    try:
        return len(Queue(QUEUE_NAME, connection=get_redis()))
    except Exception:
        return None
