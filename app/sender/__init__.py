"""Sender stub. Sending is out of scope: nothing in the app calls send()."""
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Draft, Email, Suppression
from app.services.control import daily_send_cap


def can_send(s: Session, address: str) -> bool:
    """Not suppressed, status verified (so not bounced / opted out), and under today's cap."""
    a = address.lower()
    if s.scalar(select(Suppression.id).where(Suppression.email_or_domain.in_([a, a.rsplit("@", 1)[-1]]))):
        return False
    emails = list(s.scalars(select(Email).where(Email.address == a)))
    if not emails or any(e.status in ("bounced", "opted_out") for e in emails):
        return False
    if not any(e.status == "verified" for e in emails):
        return False
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = s.scalar(select(func.count()).select_from(Draft).where(Draft.status == "sent", Draft.reviewed_at >= start)) or 0
    return sent_today < daily_send_cap(s)


def send(address: str, subject: str, body: str) -> None:
    # TODO: implement an SMTP/API sender in a later phase. Must call can_send() first and honour DRY_RUN.
    raise NotImplementedError("sending is intentionally not implemented in this phase")
