"""Outreach cadence: after you mark a first email sent, one follow-up (day 4) and one closing note (day 10) are
scheduled as drafts for your review; nothing goes out by itself. Replied / declined / done stops the rest."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Draft, Person, Suppression, now
from app.services.control import daily_send_cap
from app.services.llm.base import DraftInput
from app.services.llm.template import TemplateProvider
from app.services.profile import load_profile

CADENCE = [("followup", 4), ("final", 10)]  # kind, days after the first email; the day 4-5 / 10-12 windows are due-from dates
STOP_STATES = {"replied", "declined", "done"}


def schedule_followups(s: Session, sent: Draft) -> int:
    if sent.kind != "initial" or sent.reviewed_at is None:
        return 0
    try:
        profile = load_profile()
    except (FileNotFoundError, ValueError):
        return 0
    p, co = sent.person, sent.company
    inp = DraftInput(profile, p.full_name, p.title, p.role_type, co.name, sent.signals_used or [], p.intent or "hire",
                     co.description or "", f"{co.description or ''} {co.industry or ''}")
    made = 0
    for kind, days in CADENCE:
        if s.scalar(select(Draft.id).where(Draft.parent_id == sent.id, Draft.kind == kind)):
            continue
        s.add(Draft(person_id=p.id, company_id=co.id, subject="Re: " + sent.subject, body=TemplateProvider().followup(kind, inp),
                    prompt_version="followup-v1", llm_provider="template", signals_used=sent.signals_used, status="pending",
                    kind=kind, parent_id=sent.id, due_at=sent.reviewed_at + timedelta(days=days)))
        made += 1
    return made


def set_outreach(s: Session, person: Person, status: str) -> None:
    """Record a reply / decline / done: cancels every follow-up still waiting, and a decline suppresses the address."""
    person.outreach = status
    if status in STOP_STATES:
        for d in s.scalars(select(Draft).where(Draft.person_id == person.id, Draft.status.in_(["pending", "approved"]), Draft.kind != "initial")):
            d.status = "skipped"
    if status == "declined":
        for e in person.emails:
            if not s.scalar(select(Suppression.id).where(Suppression.email_or_domain == e.address.lower())):
                s.add(Suppression(email_or_domain=e.address.lower(), reason="declined outreach"))


def allowance(s: Session) -> tuple[int, int, int]:
    """(daily cap, sent in the last 24 hours, remaining)."""
    cap = daily_send_cap(s)
    sent = s.scalar(select(func.count()).select_from(Draft).where(Draft.status == "sent", Draft.reviewed_at >= now() - timedelta(hours=24))) or 0
    return cap, sent, max(0, cap - sent)


def ready_drafts(s: Session) -> list[Draft]:
    """Approved drafts that are due, best first: published addresses before guesses, follow-ups before new emails, then score."""
    supp = {r.lower() for r in s.scalars(select(Suppression.email_or_domain))}
    out: list[tuple[tuple[bool, bool, int], Draft]] = []
    for d in s.scalars(select(Draft).where(Draft.status == "approved", Draft.due_at.is_(None) | (Draft.due_at <= now()))):
        best = max(d.person.emails, key=lambda e: (e.confidence, -e.id), default=None)
        if best is None or best.address.lower() in supp or best.address.lower().rsplit("@", 1)[-1] in supp or d.person.outreach in STOP_STATES:
            continue
        out.append(((best.confidence < 80, d.kind == "initial", -(d.person.score or 0)), d))
    return [d for _, d in sorted(out, key=lambda x: x[0])]
