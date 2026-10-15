"""Maps Leads: local businesses (found by the extension on Google Maps) that may need a website. Stored as companies."""
import re
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import review_auth
from app.core.db import get_session
from app.models import Company, now
from app.services.control import get_setting, set_setting
from app.services.normalize import normalize_name

router = APIRouter(prefix="/leads", dependencies=[Depends(review_auth)])
STATUSES = ["new", "contacted", "replied", "quoted", "won", "lost"]
HIGH_NEED = re.compile(r"dent|clinic|doctor|salon|spa|restaurant|cafe|café|bakery|gym|fitness|tutor|coaching|school|repair|boutique|studio|lawyer|advocate|photograph", re.I)
DEFAULT_PITCH = (
    "Hi, I'm Saksham, a web developer in Delhi. I noticed {name} doesn't have a website, so people searching for a {category} "
    "online can't find your hours, services or prices. I can build you a simple one-page website, and I'm happy to make a free "
    "preview first. Examples of my work: https://dentiq-kappa.vercel.app and https://orbit-inky-psi.vercel.app . "
    "Would you like to see a preview? (Reply STOP and I won't message again.)"
)


class LeadRow(BaseModel):
    name: str
    rating: str = ""
    category_address: str = ""
    phone: str = ""
    has_website: str = "no"
    website: str = ""
    maps_url: str = ""


class IngestIn(BaseModel):
    rows: list[LeadRow]
    query: str = ""


def lead_score(c: Company) -> int:
    e = c.extra or {}
    score = 30 + (30 if not e.get("has_website") else 0) + (15 if e.get("phone") else 0) + (10 if HIGH_NEED.search(f"{c.industry or ''} {c.name}") else 0)
    m = re.search(r"(\d[\d,]*)\s*reviews?", e.get("rating", ""), re.I)
    if m and int(m.group(1).replace(",", "")) >= 20:
        score += 10  # established business, more likely to pay
    return min(100, score)


def lead_out(c: Company) -> dict[str, Any]:
    e = c.extra or {}
    return {"id": c.id, "name": c.name, "category": c.industry, "address": e.get("address") or c.city, "phone": e.get("phone", ""), "rating": e.get("rating", ""),
            "has_website": bool(e.get("has_website")), "website": c.website, "maps_url": e.get("maps_url", ""), "status": e.get("lead_status", "new"),
            "notes": e.get("notes", ""), "query": e.get("query", ""), "score": lead_score(c), "found_at": c.created_at}


def _leads(s: Session) -> list[Company]:
    return list(s.scalars(select(Company).where(Company.source == "maps").order_by(Company.id.desc())))


@router.post("/ingest")
def ingest(b: IngestIn, s: Session = Depends(get_session)) -> dict[str, int]:
    """Called by the extension: the rows it read from Google Maps. Duplicates (same name and address) are updated, not repeated."""
    new = updated = 0
    for r in b.rows:
        name = r.name.strip()
        if not name:
            continue
        parts = [p.strip() for p in r.category_address.split("·")]
        category, address = (parts[0], " ".join(parts[1:]).strip()) if len(parts) > 1 else (r.category_address.strip(), "")
        norm = normalize_name(name)
        full_address, address = address, address[:100]  # the column is 100 chars; the full text lives in extra
        co = s.scalar(select(Company).where(Company.source == "maps", Company.normalized_name == norm, Company.city == (address or None)))
        if co is None:
            co = Company(name=name[:300], normalized_name=norm[:300], source="maps", extra={"lead_status": "new"})
            s.add(co)
            new += 1
        else:
            updated += 1
        co.industry, co.city, co.fetched_at = (category or co.industry or "")[:200] or None, address or None, now()
        co.website = (r.website or "")[:500] or None
        co.extra = {**(co.extra or {}), "kind": "local_business", "address": full_address, "phone": r.phone, "rating": r.rating, "maps_url": r.maps_url,
                    "has_website": r.has_website.lower() == "yes", "query": b.query or (co.extra or {}).get("query", "")}
    s.commit()
    return {"received": len(b.rows), "new": new, "updated": updated}


@router.get("")
def list_leads(no_website: bool = False, status: str | None = None, q: str | None = None, page: int = 1, page_size: int = 100,
               s: Session = Depends(get_session)) -> dict[str, Any]:
    items = [lead_out(c) for c in _leads(s)]
    if no_website:
        items = [i for i in items if not i["has_website"]]
    if status:
        items = [i for i in items if i["status"] == status]
    if q:
        items = [i for i in items if q.lower() in f"{i['name']} {i['category']} {i['address']}".lower()]
    items.sort(key=lambda i: -i["score"])
    return {"total": len(items), "items": items[(page - 1) * page_size: page * page_size]}


@router.get("/stats")
def stats(s: Session = Depends(get_session)) -> dict[str, Any]:
    items = [lead_out(c) for c in _leads(s)]
    by: dict[str, int] = {st: 0 for st in STATUSES}
    for i in items:
        by[i["status"]] = by.get(i["status"], 0) + 1
    return {"total": len(items), "no_website": sum(1 for i in items if not i["has_website"]), "by_status": by, "recent": items[:15]}


class LeadPatch(BaseModel):
    status: Literal["new", "contacted", "replied", "quoted", "won", "lost"] | None = None
    notes: str | None = None


@router.patch("/{lead_id}")
def patch_lead(lead_id: int, b: LeadPatch, s: Session = Depends(get_session)) -> dict[str, Any]:
    c = s.get(Company, lead_id)
    if c is None or c.source != "maps":
        raise HTTPException(404, "lead not found")
    e = dict(c.extra or {})
    if b.status:
        e["lead_status"] = b.status
    if b.notes is not None:
        e["notes"] = b.notes
    c.extra = e
    s.commit()
    return lead_out(c)


class PitchIn(BaseModel):
    template: str


@router.get("/pitch")
def get_pitch(s: Session = Depends(get_session)) -> dict[str, str]:
    return {"template": get_setting(s, "maps_pitch", DEFAULT_PITCH)}


@router.put("/pitch")
def put_pitch(b: PitchIn, s: Session = Depends(get_session)) -> dict[str, str]:
    set_setting(s, "maps_pitch", b.template)
    return {"template": b.template}

