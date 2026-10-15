from sqlalchemy import select

from app.models import Company, now
from app.services.website_check import classify
from app.stages.base import StageContext


def run(ctx: StageContext) -> None:
    """Strict website check for Maps leads that are still 'pending'."""
    leads = [c for c in ctx.session.scalars(select(Company).where(Company.source == "maps").order_by(Company.id))
             if (c.extra or {}).get("website_status", "pending") == "pending"]
    leads = leads[: ctx.limit] if ctx.limit else leads
    client = ctx.client("verify_websites", 1.0)
    for i, c in enumerate(leads, 1):
        ctx.check()
        e = dict(c.extra or {})
        v = classify(c.name, e.get("phone", ""), e.get("maps_website", ""), e.get("links", []), bool(e.get("detail_read")), client)
        e.update(website_status=v.status, website_evidence=v.evidence, website_checked_at=now().isoformat(), has_website=v.status in ("has_site", "probable_site"))
        if v.url:
            e["website_url"] = v.url
            c.website = v.url
        c.extra = e
        ctx.count(f"site_{v.status}")
        if not ctx.dry_run:
            ctx.session.commit()  # short transactions: Neon drops connections left idle inside a long one while we fetch other sites
        ctx.progress(i, len(leads))
