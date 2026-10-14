"""Kill switch, cancel flags and typed app settings, all persisted in app_settings."""
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AppSetting

ALLOWED_SETTINGS = {"dry_run_default", "daily_send_cap"}


class Cancelled(Exception):
    pass


class KillSwitchOn(Exception):
    pass


def get_setting(s: Session, key: str, default: Any = None) -> Any:
    row = s.scalar(select(AppSetting).where(AppSetting.key == key))
    return row.value if row else default


def set_setting(s: Session, key: str, value: Any) -> None:
    row = s.scalar(select(AppSetting).where(AppSetting.key == key))
    if row:
        row.value = value
    else:
        s.add(AppSetting(key=key, value=value))
    s.commit()


def kill_switch_on(s: Session) -> bool:
    return bool(get_setting(s, "kill_switch", False))


def dry_run_default(s: Session) -> bool:
    return bool(get_setting(s, "dry_run_default", get_settings().DRY_RUN_DEFAULT))


def daily_send_cap(s: Session) -> int:
    return int(get_setting(s, "daily_send_cap", get_settings().DAILY_SEND_CAP))


def request_cancel(s: Session, job_id: int) -> None:
    set_setting(s, f"cancel:{job_id}", True)


def cancel_requested(s: Session, job_id: int) -> bool:
    return bool(get_setting(s, f"cancel:{job_id}", False))


def clear_cancel(s: Session, job_id: int) -> None:
    row = s.scalar(select(AppSetting).where(AppSetting.key == f"cancel:{job_id}"))
    if row:
        s.delete(row)
        s.commit()
