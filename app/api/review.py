from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.core.auth import review_auth
from app.core.db import get_session
from app.models import Company, Draft, Email, Person, Signal, Suppression, now

router = APIRouter(dependencies=[Depends(review_auth)])


def email_out(e: Email) -> dict[str, Any]:
    return {"id": e.id, "address": e.address, "confidence": e.confidence, "status": e.status,
            "smtp_status": e.smtp_status, "mx_valid": e.mx_valid, "pattern_used": e.pattern_used, "source": e.source}


def person_out(p: Person, with_company: bool = False) -> dict[str, Any]:
    d = {"id": p.id, "company_id": p.company_id, "full_name": p.full_name, "title": p.title, "role_type": p.role_type,
         "score": p.score, "intent": p.intent, "reason": p.reason, "linkedin_url": p.linkedin_url, "twitter_url": p.twitter_url, "github_url": p.github_url, "source": p.source,
         "emails": [email_out(e) for e in sorted(p.emails, key=lambda e: -e.confidence)]}
    if with_company:
        d["company_name"] = p.company.name
    return d


def signal_out(sg: Signal) -> dict[str, Any]:
    return {"id": sg.id, "type": sg.type, "value": sg.value, "url": sg.url, "observed_at": sg.observed_at, "source": sg.source}


def company_out(c: Company) -> dict[str, Any]:
    return {k: getattr(c, k) for k in ("id", "name", "domain", "website", "stage", "industry", "country", "city",
                                         "employee_range", "is_hiring", "description", "source", "fetched_at")}


SORTABLE = {"name", "stage", "country", "industry", "is_hiring", "fetched_at", "id"}


@router.get("/companies")
def list_companies(country: str | None = None, stage: str | None = None, is_hiring: bool | None = None,
                   source: str | None = None, sort: str = "name", order: Literal["asc", "desc"] = "asc",
                   page: int = 1, page_size: int = 50, s: Session = Depends(get_session)) -> dict[str, Any]:
    q = select(Company)
    for col, val in (("country", country), ("stage", stage), ("is_hiring", is_hiring), ("source", source)):
        if val is not None:
            q = q.where(getattr(Company, col) == val)
    total = s.scalar(select(func.count()).select_from(q.subquery())) or 0
    col = getattr(Company, sort if sort in SORTABLE else "name")
    rows = s.scalars(q.order_by(asc(col) if order == "asc" else desc(col)).offset((page - 1) * page_size).limit(page_size))
    return {"total": total, "items": [company_out(c) for c in rows]}


@router.get("/companies/{company_id}")
def get_company(company_id: int, s: Session = Depends(get_session)) -> dict[str, Any]:
    c = s.get(Company, company_id)
    if c is None:
        raise HTTPException(404, "company not found")
    return {**company_out(c), "people": [person_out(p) for p in c.people],
            "signals": [signal_out(x) for x in sorted(c.signals, key=lambda x: x.observed_at or now(), reverse=True)]}


class LinkedinCsv(BaseModel):
    csv: str


@router.post("/import/linkedin")
def import_linkedin(b: LinkedinCsv, s: Session = Depends(get_session)) -> dict[str, int]:
    """Upload the text of your own Connections.csv; each connection becomes a contact (flagged as a connection)."""
    from app.services.linkedin_import import import_connections, parse_connections

    try:
        conns = parse_connections(b.csv)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"rows": len(conns), **import_connections(s, conns)}


@router.get("/jobs")
def list_jobs(q: str | None = None, page: int = 1, page_size: int = 50, s: Session = Depends(get_session)) -> dict[str, Any]:
    """Jobs that matched the saved search (title keyword + remote): one row per job signal, newest first."""
    base = select(Signal, Company).join(Company, Company.id == Signal.company_id).where(Signal.type == "hiring", Signal.value.like("Job: %"))
    if q:
        base = base.where(Signal.value.ilike(f"%{q}%") | Company.name.ilike(f"%{q}%"))
    total = s.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = s.execute(base.order_by(Signal.observed_at.desc().nulls_last(), Signal.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = []
    for sg, co in rows:
        people = [p for p in co.people if p.emails]
        best = max(people, key=lambda p: p.score, default=None)
        items.append({"id": sg.id, "job": sg.value[5:], "apply_url": sg.url, "source": sg.source, "observed_at": sg.observed_at,
                      "company": {"id": co.id, "name": co.name, "domain": co.domain}, "contacts": len(co.people),
                      "best_contact": {"name": best.full_name, "title": best.title, "email": max(best.emails, key=lambda e: e.confidence).address,
                                       "confidence": max(e.confidence for e in best.emails)} if best else None})
    return {"total": total, "items": items}


@router.get("/people")
def list_people(role_type: str | None = None, company_id: int | None = None, email_status: str | None = None,
                intent: str | None = None, min_score: int = 0, s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    q = select(Person).where(Person.score >= min_score).order_by(Person.score.desc(), Person.id)
    if intent:
        q = q.where(Person.intent == intent)
    if role_type:
        q = q.where(Person.role_type == role_type)
    if company_id:
        q = q.where(Person.company_id == company_id)
    if email_status:
        q = q.where(Person.id.in_(select(Email.person_id).where(Email.status == email_status)))
    return [person_out(p, with_company=True) for p in s.scalars(q.limit(500))]


def draft_out(d: Draft) -> dict[str, Any]:
    best = max(d.person.emails, key=lambda e: e.confidence, default=None)
    return {"id": d.id, "status": d.status, "subject": d.subject, "body": d.body, "prompt_version": d.prompt_version,
            "llm_provider": d.llm_provider, "signals_used": d.signals_used, "created_at": d.created_at,
            "reviewed_at": d.reviewed_at, "person": {"id": d.person.id, "full_name": d.person.full_name, "title": d.person.title},
            "company": {"id": d.company.id, "name": d.company.name}, "to": best.address if best else None, "to_confidence": best.confidence if best else 0,
            "to_status": best.status if best else None, "intent": d.person.intent, "score": d.person.score}


@router.get("/drafts")
def list_drafts(status: str | None = None, s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    q = select(Draft).order_by(Draft.id)
    if status:
        q = q.where(Draft.status == status)
    return [draft_out(d) for d in s.scalars(q.limit(500))]


class DraftPatch(BaseModel):
    action: Literal["approve", "reject", "skip", "edit", "sent"] | None = None
    subject: str | None = None
    body: str | None = None


@router.patch("/drafts/{draft_id}")
def patch_draft(draft_id: int, patch: DraftPatch, s: Session = Depends(get_session)) -> dict[str, Any]:
    d = s.get(Draft, draft_id)
    if d is None:
        raise HTTPException(404, "draft not found")
    if d.status == "sent":
        raise HTTPException(409, "draft already marked sent")
    if patch.action == "sent" and d.status != "approved":
        raise HTTPException(409, "approve the draft before marking it sent")
    if patch.subject is not None:
        d.subject = patch.subject
    if patch.body is not None:
        d.body = patch.body
    if patch.action in ("approve", "reject", "skip", "sent"):
        if patch.action == "approve":
            to = [e.address.lower() for e in d.person.emails]
            keys = to + [a.rsplit("@", 1)[-1] for a in to]
            if s.scalar(select(Suppression.id).where(Suppression.email_or_domain.in_(keys))):
                raise HTTPException(409, "recipient is on the suppression list")
        d.status = {"approve": "approved", "reject": "rejected", "skip": "skipped", "sent": "sent"}[patch.action]  # "sent" = you mailed it yourself
        d.reviewed_at = now()
    s.commit()
    return draft_out(d)


class SuppressionIn(BaseModel):
    email_or_domain: str
    reason: str | None = None


@router.get("/suppression")
def list_suppression(s: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [{"id": r.id, "email_or_domain": r.email_or_domain, "reason": r.reason, "created_at": r.created_at}
            for r in s.scalars(select(Suppression).order_by(Suppression.id.desc()))]


@router.post("/suppression", status_code=201)
def add_suppression(body: SuppressionIn, s: Session = Depends(get_session)) -> dict[str, Any]:
    key = body.email_or_domain.strip().lower()
    if not key or " " in key:
        raise HTTPException(422, "provide an email address or a domain")
    if s.scalar(select(Suppression.id).where(Suppression.email_or_domain == key)):
        raise HTTPException(409, "already suppressed")
    row = Suppression(email_or_domain=key, reason=body.reason)
    s.add(row)
    s.commit()
    return {"id": row.id, "email_or_domain": key, "reason": body.reason}


@router.delete("/suppression/{sid}", status_code=204)
def delete_suppression(sid: int, s: Session = Depends(get_session)) -> None:
    row = s.get(Suppression, sid)
    if row is None:
        raise HTTPException(404, "not found")
    s.delete(row)
    s.commit()
