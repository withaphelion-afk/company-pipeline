from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Person, Signal, now
from app.services.normalize import classify_role, domain_of, normalize_name
from app.sources.base import CompanyRaw, PersonRaw, SignalRaw

_FIELDS = ("website", "stage", "industry", "country", "city", "employee_range", "description")


def upsert_company(s: Session, raw: CompanyRaw) -> tuple[Company, bool]:
    """Upsert by canonical domain; domainless records merge on normalized name."""
    norm = normalize_name(raw.name)
    domain = domain_of(raw.website)
    co = s.scalar(select(Company).where(Company.domain == domain)) if domain else None
    if co is None:
        q = select(Company).where(Company.normalized_name == norm)
        if domain:
            q = q.where(Company.domain.is_(None))
        co = s.scalars(q).first()
    created = co is None
    if co is None:
        co = Company(name=raw.name, normalized_name=norm, extra={})
        s.add(co)
    if domain and not co.domain:
        co.domain = domain
    for f in _FIELDS:
        v = getattr(raw, f)
        if v:
            setattr(co, f, v)
    co.is_hiring = co.is_hiring or raw.is_hiring
    co.extra = {**(co.extra or {}), **raw.extra}
    co.source, co.fetched_at = raw.source, now()
    s.flush()
    return co, created


def upsert_person(s: Session, company: Company, raw: PersonRaw) -> tuple[Person, bool]:
    p = s.scalar(select(Person).where(Person.company_id == company.id, Person.full_name == raw.full_name))
    created = p is None
    if p is None:
        p = Person(company_id=company.id, full_name=raw.full_name, extra={})
        s.add(p)
    p.title = raw.title or p.title
    p.role_type = classify_role(p.title)
    for f in ("linkedin_url", "twitter_url", "github_url"):
        if getattr(raw, f):
            setattr(p, f, getattr(raw, f))
    if raw.email:
        p.extra = {**(p.extra or {}), "found_email": raw.email, "found_email_url": raw.email_url}
    p.source, p.fetched_at = raw.source, now()
    s.flush()
    return p, created


def upsert_signal(s: Session, company: Company, raw: SignalRaw) -> bool:
    key = Signal.url == raw.url if raw.url else Signal.value == raw.value
    if s.scalar(select(Signal).where(Signal.company_id == company.id, Signal.type == raw.type, key)):
        return False
    s.add(Signal(company_id=company.id, type=raw.type, value=raw.value, url=raw.url, observed_at=raw.observed_at or now(), source=raw.source))
    s.flush()
    return True
