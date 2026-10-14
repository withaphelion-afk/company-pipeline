"""Gmail API sender (local use). Scope is gmail.send only. Credentials live in credentials.json / token.json, both git-ignored.

Rules enforced here: only approved, due drafts; one separate message per recipient (a single To, no CC/BCC); the daily allowance;
suppressed addresses skipped; dry run available (and required by the API caller).
"""
import base64
import random
import time
from collections.abc import Callable
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models import Draft, now
from app.services.control import get_setting
from app.services.outreach import allowance, ready_drafts, schedule_followups

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CREDENTIALS = Path("credentials.json")
TOKEN = Path("token.json")


class NotAuthorized(Exception):
    pass


def is_authorized() -> bool:
    return TOKEN.exists()


def load_credentials(interactive: bool = False) -> Any:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not interactive:
            raise NotAuthorized("Gmail is not authorized yet: run `python -m pipeline gmail-auth` once")
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES).run_local_server(port=0)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return creds


def build_service() -> Any:
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=load_credentials(), cache_discovery=False)


def make_raw(to: str, sender: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["To"] = to  # exactly one recipient: no Cc, no Bcc
    msg["From"] = sender
    msg["Subject"] = subject
    msg["Importance"] = "high"  # marked important for the recipient (standard headers; Gmail/Outlook show the flag)
    msg["X-Priority"] = "1"
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_approved(
    s: Session,
    service: Any,
    dry_run: bool,
    limit: int | None = None,
    pause: tuple[float, float] = (8.0, 15.0),
    sleep: Callable[[float], None] = time.sleep,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Send (or preview) the approved drafts that are due, best first, up to today's allowance."""
    results: list[dict[str, Any]] = []
    # gmail.send cannot read the profile, so the account is whoever authorized token.json; From is the saved "send from"
    account = get_setting(s, "send_from", "") or "me"
    _, _, remaining = allowance(s)
    todo: list[Draft] = ready_drafts(s)[: min(remaining, limit) if limit else remaining]
    for i, d in enumerate(todo):
        to = max(d.person.emails, key=lambda e: (e.confidence, -e.id)).address
        row: dict[str, Any] = {"id": d.id, "to": to, "name": d.person.full_name, "subject": d.subject, "kind": d.kind, "status": "preview"}
        if not dry_run:
            try:
                msg_id = service.users().messages().send(userId="me", body={"raw": make_raw(to, account, d.subject, d.body)}).execute()["id"]
            except Exception as e:  # stop at the first failure rather than hammer the API
                row.update(status="error", error=str(e)[:300])
                results.append(row)
                if on_result:
                    on_result(row)
                break
            d.status, d.reviewed_at = "sent", now()
            if d.person.outreach == "none":
                d.person.outreach = "contacted"
            schedule_followups(s, d)
            s.commit()
            row.update(status="sent", gmail_id=msg_id)
        results.append(row)
        if on_result:
            on_result(row)
        if not dry_run and i < len(todo) - 1:
            sleep(random.uniform(*pause))  # small human-like gap between separate emails
    return results
