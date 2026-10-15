"""Maps Leads: local businesses (found by the extension on Google Maps) that may need a website. Stored as companies."""
import re
import threading
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import ingest_auth, review_auth
from app.core.db import get_session
from app.models import AppSetting, Company, now
from app.services.control import get_setting, set_setting
from app.services.normalize import normalize_name
from app.services.website_check import is_aggregator

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
    links: list[str] = []  # external links found on the listing (used by the strict website check)
    detail_read: bool = False  # True when the business's own detail panel was opened and read


class IngestIn(BaseModel):
    rows: list[LeadRow]
    query: str = ""


def site_status(e: dict[str, Any]) -> str:
    """has_site | probable_site | none | unknown | pending (old rows without a status are re-checked)."""
    return e.get("website_status") or ("has_site" if e.get("has_website") else "pending")


def lead_score(c: Company) -> int:
    e = c.extra or {}
    st = site_status(e)
    score = 30 + (30 if st == "none" else 10 if st in ("unknown", "pending", "probable_site") else 0) + (15 if e.get("phone") else 0) + (10 if HIGH_NEED.search(f"{c.industry or ''} {c.name}") else 0)
    m = re.search(r"(\d[\d,]*)\s*reviews?", e.get("rating", ""), re.I)
    if m and int(m.group(1).replace(",", "")) >= 20:
        score += 10  # established business, more likely to pay
    return min(100, score)


def lead_out(c: Company) -> dict[str, Any]:
    e = c.extra or {}
    return {"id": c.id, "name": c.name, "category": c.industry, "address": e.get("address") or c.city, "phone": e.get("phone", ""), "rating": e.get("rating", ""),
            "has_website": site_status(e) in ("has_site", "probable_site"), "website_status": site_status(e),
            "website_evidence": e.get("website_evidence", ""), "website": c.website, "maps_url": e.get("maps_url", ""), "status": e.get("lead_status", "new"),
            "notes": e.get("notes", ""), "queries": e.get("queries") or ([e["query"].lower()] if e.get("query") else []), "score": lead_score(c), "found_at": c.created_at}


def _leads(s: Session) -> list[Company]:
    return list(s.scalars(select(Company).where(Company.source == "maps").order_by(Company.id.desc())))


@router.post("/ingest")
def ingest(b: IngestIn, s: Session = Depends(get_session), _: None = Depends(ingest_auth)) -> dict[str, int]:
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
        e0 = co.extra or {}
        real_site = bool(r.website) and not is_aggregator(r.website)
        old = e0.get("website_status")
        status = "has_site" if real_site else ("pending" if old in (None, "pending", "unknown") else old)
        co.extra = {**e0, "kind": "local_business", "address": full_address, "phone": r.phone, "rating": r.rating, "maps_url": r.maps_url,
                    "maps_website": r.website, "links": r.links[:20], "detail_read": r.detail_read or bool(e0.get("detail_read")),
                    "website_status": status, "has_website": status in ("has_site", "probable_site"),
                    **({"website_evidence": "listed on Google Maps", "website_url": r.website} if real_site else {}),
                    "queries": sorted(set((co.extra or {}).get("queries", [])) | ({b.query.strip().lower()} if b.query.strip() else set()))}
    s.commit()
    return {"received": len(b.rows), "new": new, "updated": updated}


@router.get("")
def list_leads(no_website: bool = False, status: str | None = None, q: str | None = None, search: str | None = None, site: Literal["any", "none", "has", "probable", "unknown"] = "any", sort: str = "score", order: Literal["asc", "desc"] = "desc", page: int = 1, page_size: int = 100,
               s: Session = Depends(get_session)) -> dict[str, Any]:
    items = [lead_out(c) for c in _leads(s)]
    want = {"none": ("none",), "has": ("has_site",), "probable": ("probable_site",), "unknown": ("unknown", "pending")}
    if no_website:
        site = "none"
    if site != "any":
        items = [i for i in items if i["website_status"] in want[site]]
    if status:
        items = [i for i in items if i["status"] == status]
    if search:
        items = [i for i in items if search.lower() in i["queries"]]
    if q:
        items = [i for i in items if q.lower() in f"{i['name']} {i['category']} {i['address']}".lower()]
    def key(i: dict[str, Any]) -> Any:
        if sort == "reviews":
            m = re.search(r"([\d,]+)\s*reviews?", i["rating"], re.I)
            return int(m.group(1).replace(",", "")) if m else 0
        if sort == "website":
            return i["website_status"]
        if sort == "found":
            return str(i["found_at"] or "")
        if sort in ("name", "category", "address", "phone", "status"):
            return str(i.get(sort) or "").lower()
        return i["score"]

    items.sort(key=key, reverse=order == "desc")
    return {"total": len(items), "items": items[(page - 1) * page_size: page * page_size]}


@router.get("/stats")
def stats(s: Session = Depends(get_session)) -> dict[str, Any]:
    items = [lead_out(c) for c in _leads(s)]
    by: dict[str, int] = {st: 0 for st in STATUSES}
    for i in items:
        by[i["status"]] = by.get(i["status"], 0) + 1
    searches: dict[str, dict[str, int]] = {}
    for i in items:
        for qy in i["queries"]:
            row = searches.setdefault(qy, {"total": 0, "no_website": 0})
            row["total"] += 1
            row["no_website"] += 1 if i["website_status"] == "none" else 0
    return {"total": len(items), "no_website": sum(1 for i in items if i["website_status"] == "none"),
            "unverified": sum(1 for i in items if i["website_status"] in ("unknown", "pending")), "by_status": by, "recent": items[:15],
            "searches": [{"query": k, **v} for k, v in sorted(searches.items())]}


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




# --- search queue (what the crawler works through) --------------------------------------------------------------
QUEUE_KEY = "maps_queue"
HIGH_TICKET = ["skin clinic", "hair transplant clinic", "dental implant clinic", "IVF clinic", "physiotherapy clinic",
               "interior designer", "wedding photographer", "event planner", "coaching classes"]
DELHI_AREAS = ["Saket", "Greater Kailash", "Defence Colony", "Vasant Kunj", "Hauz Khas", "Connaught Place", "Lajpat Nagar", "Dwarka",
               "Rohini", "Pitampura", "Janakpuri", "Karol Bagh", "Preet Vihar", "Vasant Vihar", "Safdarjung Enclave", "Punjabi Bagh"]
STALE_MINUTES = 90


class QueueAdd(BaseModel):
    keywords: list[str]
    areas: list[str]  # for example "Saket, Delhi"


class QueueDone(BaseModel):
    found: int = 0
    new: int = 0
    error: str | None = None


def _queue(s: Session) -> list[dict[str, Any]]:
    return list(get_setting(s, QUEUE_KEY, []) or [])


@router.get("/queue")
def get_queue(s: Session = Depends(get_session)) -> dict[str, Any]:
    return {"items": _queue(s), "starter": {"keywords": HIGH_TICKET, "areas": DELHI_AREAS}}


@router.post("/queue")
def add_queue(b: QueueAdd, s: Session = Depends(get_session)) -> dict[str, int]:
    q = _queue(s)
    have = {i["query"] for i in q}
    nid = max((i["id"] for i in q), default=0)
    added = 0
    for kw in (k.strip() for k in b.keywords if k.strip()):
        for area in (a.strip() for a in b.areas if a.strip()):
            query = f"{kw} in {area}"
            if query.lower() in have:
                continue
            nid += 1
            q.append({"id": nid, "keyword": kw, "area": area, "query": query.lower(), "status": "pending", "found": 0, "new": 0,
                      "last_run_at": None, "error": None})
            have.add(query.lower())
            added += 1
    set_setting(s, QUEUE_KEY, q)
    return {"added": added, "total": len(q)}


@router.delete("/queue/{qid}", status_code=204)
def delete_queue(qid: int, s: Session = Depends(get_session)) -> None:
    set_setting(s, QUEUE_KEY, [i for i in _queue(s) if i["id"] != qid])


@router.post("/queue/{qid}/reset")
def reset_queue(qid: int, s: Session = Depends(get_session)) -> dict[str, Any]:
    q = _queue(s)
    for i in q:
        if i["id"] == qid:
            i.update(status="pending", error=None)
    set_setting(s, QUEUE_KEY, q)
    return {"id": qid}


_claim_lock = threading.Lock()  # one claim at a time inside this process; the row lock below covers other processes


@router.post("/queue/next")
def claim_next(s: Session = Depends(get_session), _: None = Depends(ingest_auth)) -> dict[str, Any]:
    """The crawler asks for its next search. A search stuck 'running' for over 90 minutes (a crashed run) is handed out again."""
    with _claim_lock:
        return _claim(s)


def _claim(s: Session) -> dict[str, Any]:
    from datetime import UTC, datetime, timedelta

    row = s.scalar(select(AppSetting).where(AppSetting.key == QUEUE_KEY).with_for_update())  # lock: parallel crawlers must never get the same search
    if row is None:
        return {"item": None}
    q = [dict(i) for i in (row.value or [])]
    cutoff = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
    for i in q:
        stale = i["status"] == "running" and i.get("last_run_at") and datetime.fromisoformat(i["last_run_at"]) < cutoff
        if i["status"] == "pending" or stale:
            i.update(status="running", last_run_at=datetime.now(UTC).isoformat(), error=None)
            row.value = q
            s.commit()
            return {"item": i}
    s.rollback()
    return {"item": None}


@router.post("/queue/{qid}/done")
def finish_queue(qid: int, b: QueueDone, s: Session = Depends(get_session), _: None = Depends(ingest_auth)) -> dict[str, Any]:
    q = _queue(s)
    for i in q:
        if i["id"] == qid:
            i.update(status="error" if b.error else "done", found=b.found, new=b.new, error=b.error)
    set_setting(s, QUEUE_KEY, q)
    return {"id": qid}
