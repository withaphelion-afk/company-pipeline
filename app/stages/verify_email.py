from sqlalchemy import select

from app.models import Email, Person, now
from app.services import dns_tools, smtp_probe
from app.services.normalize import candidate_emails, confidence
from app.stages.base import StageContext


def _store(ctx: StageContext, person: Person, address: str, pattern: str | None, conf: int, smtp: str,
           mx: bool | None, source: str | None, status: str) -> None:
    e = ctx.session.scalar(select(Email).where(Email.person_id == person.id, Email.address == address))
    if e is None:
        e = Email(person_id=person.id, address=address)
        ctx.session.add(e)
    e.pattern_used, e.confidence, e.smtp_status, e.mx_valid, e.source, e.status = pattern, conf, smtp, mx, source, status
    e.verified_at = now() if status == "verified" else None
    ctx.count("emails_" + status)


def run(ctx: StageContext) -> None:
    supp = ctx.suppressed()
    people = [
        p for p in ctx.session.scalars(select(Person).order_by(Person.id))
        if p.company.domain and not p.emails
    ]
    people = people[: ctx.limit] if ctx.limit else people
    mx_cache: dict[str, bool] = {}
    catch_all: set[str] = set()
    for i, p in enumerate(people, 1):
        ctx.check()
        domain = p.company.domain or ""
        found = (p.extra or {}).get("found_email")
        if found:  # published on the company's own page
            if found not in supp:
                _store(ctx, p, found, "published", confidence("direct", ""), "not_checked", None,
                       p.extra.get("found_email_url"), "verified")
            ctx.progress(i, len(people))
            continue
        if domain in supp:
            ctx.count("skipped_suppressed")
            ctx.progress(i, len(people))
            continue
        if domain not in mx_cache:
            mx_cache[domain] = dns_tools.has_mx(domain)
        if not mx_cache[domain]:
            ctx.count("mx_invalid_domain")
            ctx.progress(i, len(people))
            continue
        probe = not ctx.dry_run and smtp_probe.probe_allowed(domain)
        for address, pattern in candidate_emails(p.full_name, domain):
            if address in supp:
                continue
            if not probe:
                _store(ctx, p, address, pattern, confidence("generated", "not_checked"), "not_checked", True, "pattern", "unverified")
                continue
            result = "catch_all" if domain in catch_all else smtp_probe.check_address(address)
            if result == "catch_all":
                catch_all.add(domain)
                # never verified: a catch-all accepts anything
                _store(ctx, p, address, pattern, confidence("generated", "catch_all"), "catch_all", True, "smtp", "unverified")
                break
            if result == "valid":
                _store(ctx, p, address, pattern, confidence("generated", "valid"), "valid", True, "smtp", "verified")
                break
            if result == "unknown":
                _store(ctx, p, address, pattern, confidence("generated", "unknown"), "unknown", True, "smtp", "unverified")
        ctx.progress(i, len(people))
