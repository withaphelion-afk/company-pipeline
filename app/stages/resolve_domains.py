from sqlalchemy import select

from app.models import Company
from app.services.dns_tools import has_mx
from app.services.normalize import name_slug
from app.stages.base import StageContext

TLDS = ["com", "io", "ai", "in"]


def run(ctx: StageContext) -> None:
    if ctx.from_cache:
        ctx.log("warn", "resolve_domains needs live HEAD/MX checks; skipped in --from-cache mode")
        return
    q = select(Company).where(Company.domain.is_(None))
    todo = [c for c in ctx.session.scalars(q) if not (c.extra or {}).get("domain_unresolved")]
    todo = todo[: ctx.limit] if ctx.limit else todo
    client = ctx.client("resolve_domains")
    for i, co in enumerate(todo, 1):
        ctx.check()
        slug = name_slug(co.name)
        found = None
        for tld in TLDS if slug else []:
            d = f"{slug}.{tld}"
            if client.head_ok(f"https://{d}") and has_mx(d):
                found = d
                break
        taken = found and ctx.session.scalar(select(Company.id).where(Company.domain == found))
        if found and not taken:
            co.domain, co.website = found, f"https://{found}"
            ctx.count("resolved")
        else:  # mark rather than guess
            co.extra = {**(co.extra or {}), "domain_unresolved": True}
            ctx.count("unresolved")
        ctx.progress(i, len(todo))
