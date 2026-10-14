from sqlalchemy import select

from app.models import Company
from app.services.dedupe import upsert_person
from app.sources import REGISTRY, Source
from app.stages.base import StageContext


def _people_sources(ctx: StageContext) -> list[str]:
    if ctx.source_name:
        return [ctx.source_name]
    extra = [n for n, c in REGISTRY.items() if c.fetch_people is not Source.fetch_people and n != "company_site"]
    return ["company_site", *ctx.enabled_sources(extra)]


def run(ctx: StageContext) -> None:
    q = select(Company).where(Company.domain.is_not(None)).order_by(Company.id)
    companies = list(ctx.session.scalars(q.limit(ctx.limit) if ctx.limit else q))
    names = _people_sources(ctx)
    errors = 0
    for i, co in enumerate(companies, 1):
        for name in names:
            ctx.check()
            try:
                for raw in ctx.source(name).fetch_people(co):
                    _, created = upsert_person(ctx.session, co, raw)
                    ctx.count("people_created" if created else "people_updated")
            except Exception as e:
                errors += 1
                ctx.log("error", f"{name}: {co.domain}: {e}")
        ctx.progress(i, len(companies), errors)
