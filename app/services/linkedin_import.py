"""Import the user's own LinkedIn "Connections.csv" (Settings > Get a copy of your data). No scraping, no network."""
import csv
import io
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Email, now
from app.services.dedupe import upsert_company, upsert_person
from app.sources.base import CompanyRaw, PersonRaw


@dataclass
class Connection:
    first: str
    last: str
    url: str
    email: str
    company: str
    position: str


def parse_connections(text: str) -> list[Connection]:
    """LinkedIn puts a few note lines above the header row, so find the row that starts with First Name."""
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    start = next((i for i, r in enumerate(rows) if r and r[0].strip().lower() == "first name"), None)
    if start is None:
        raise ValueError("this does not look like LinkedIn's Connections.csv (no 'First Name' header row)")
    head = [h.strip().lower() for h in rows[start]]
    col = {name: head.index(name) for name in ("first name", "last name", "url", "email address", "company", "position") if name in head}
    out = []
    for r in rows[start + 1:]:
        def g(k: str, r: list[str] = r) -> str:
            return r[col[k]].strip() if k in col and col[k] < len(r) else ""
        if g("first name") or g("last name"):
            out.append(Connection(g("first name"), g("last name"), g("url"), g("email address"), g("company"), g("position")))
    return out


def import_connections(s: Session, conns: list[Connection]) -> dict[str, int]:
    done = {"imported": 0, "skipped_no_company": 0, "with_email": 0}
    for c in conns:
        if not c.company:
            done["skipped_no_company"] += 1
            continue
        co, _ = upsert_company(s, CompanyRaw(name=c.company, source="linkedin_export"))
        p, _ = upsert_person(s, co, PersonRaw(full_name=f"{c.first} {c.last}".strip(), source="linkedin_export", title=c.position or None,
                                                linkedin_url=c.url or None))
        p.extra = {**(p.extra or {}), "connection": True}
        if c.email and not s.scalar(select(Email.id).where(Email.person_id == p.id, Email.address == c.email.lower())):
            s.add(Email(person_id=p.id, address=c.email.lower(), confidence=90, smtp_status="not_checked", status="verified",
                        source="linkedin export (shared by the connection)", verified_at=now()))
            done["with_email"] += 1
        done["imported"] += 1
    s.commit()
    return done
