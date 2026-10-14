from sqlalchemy import select

from app.models import Company
from app.services.dedupe import upsert_signal
from app.sources import SIGNAL_SOURCES
from app.stages.base import StageContext


def run(ctx: StageContext) -> None:
    names = ctx.enabled_sources(SIGNAL_SOURCES)
    if not ctx.source_name and "company_site" not in names:
        names.insert(0, "company_site")  # finds the job board + latest post; robots-gated, no config needed
    companies = [c for c in ctx.session.scalars(select(Company).order_by(Company.id)) if not (c.extra or {}).get("enriched")]
    companies = companies[: ctx.limit] if ctx.limit else companies
    errors = 0
    for i, co in enumerate(companies, 1):
        for name in names:
            ctx.check()
            try:
                for raw in ctx.source(name).fetch_signals(co):
                    if upsert_signal(ctx.session, co, raw):
                        ctx.count(f"signals_{raw.type}")
                    if raw.type == "hiring":
                        co.is_hiring = True
            except Exception as e:
                errors += 1
                ctx.log("error", f"{name}: {co.name}: {e}")
        co.extra = {**(co.extra or {}), "enriched": True}
        ctx.progress(i, len(companies), errors)
