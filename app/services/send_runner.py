"""Runs a Gmail API send in a background thread so the UI can poll progress. One run at a time."""
import threading
from typing import Any

from app.core.db import SessionLocal
from app.sender import gmail

_lock = threading.Lock()
_state: dict[str, Any] = {"running": False, "dry_run": None, "results": [], "error": None, "done": False}


class Busy(Exception):
    pass


def status() -> dict[str, Any]:
    return {**_state, "results": list(_state["results"]), "authorized": gmail.is_authorized()}


def _run(dry_run: bool, limit: int | None) -> None:
    try:
        with SessionLocal() as s:
            service = None if dry_run else gmail.build_service()
            gmail.send_approved(s, service, dry_run, limit, on_result=_state["results"].append)
    except Exception as e:
        _state["error"] = str(e)[:400]
    finally:
        _state.update(running=False, done=True)


def start(dry_run: bool, limit: int | None) -> None:
    if not dry_run and not gmail.is_authorized():
        raise gmail.NotAuthorized("Gmail is not authorized yet: run `python -m pipeline gmail-auth` once")
    with _lock:
        if _state["running"]:
            raise Busy("a send is already running")
        _state.update(running=True, dry_run=dry_run, results=[], error=None, done=False)
    threading.Thread(target=_run, args=(dry_run, limit), daemon=True).start()
