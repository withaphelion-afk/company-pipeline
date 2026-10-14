from datetime import UTC, datetime, timedelta

from apscheduler.triggers.cron import CronTrigger

MIN_INTERVAL_MINUTES = 15
PRESETS = {"every hour": "0 * * * *", "daily at 06:00": "0 6 * * *", "weekly on Monday": "0 6 * * 1"}


def validate_cron(expr: str) -> CronTrigger:
    """Parse a 5-field cron; reject anything that fires more often than every 15 minutes."""
    try:
        trig = CronTrigger.from_crontab(expr)
    except ValueError as e:
        raise ValueError(f"invalid cron expression: {e}") from e
    t = datetime.now(UTC)
    prev = None
    for _ in range(60):
        nxt = trig.get_next_fire_time(None, t)
        if nxt is None:
            break
        if prev and (nxt - prev).total_seconds() < MIN_INTERVAL_MINUTES * 60:
            raise ValueError(f"runs more often than every {MIN_INTERVAL_MINUTES} minutes")
        prev, t = nxt, nxt + timedelta(seconds=1)
    return trig


def next_run(expr: str) -> datetime | None:
    return validate_cron(expr).get_next_fire_time(None, datetime.now(UTC))
