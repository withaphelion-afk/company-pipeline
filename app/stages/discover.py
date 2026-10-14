from app.services.dedupe import upsert_company
from app.sources import SEED_SOURCES
from app.stages.base import StageContext


def run(ctx: StageContext) -> None:
    names = ctx.enabled_sources(SEED_SOURCES)
    if not names:
        ctx.log("warn", "no enabled seed sources (enable one under Sources, or pass --source)")
        return
    done = errors = new = 0
    for name in names:
        src = ctx.source(name)
        if src.is_stub:
            ctx.log("warn", f"{name} is a stub and cannot run")
            continue
        missing = src.missing_config(src.filters)
        if missing:
            ctx.log("error", f"{name}: missing config {missing}")
            errors += 1
            continue
        ctx.log("info", f"discover from {name}")
        for raw in src.fetch_companies():
            ctx.check()
            try:
                _, created = upsert_company(ctx.session, raw)
                ctx.count("companies_created" if created else "companies_updated")
                new += created
            except Exception as e:  # one bad record must not kill the run
                errors += 1
                ctx.log("error", f"{name}: {raw.name}: {e}")
            done += 1
            ctx.progress(new, ctx.limit or done, errors)
            if ctx.limit and new >= ctx.limit:  # limit = new companies, so repeated runs page through a source
                return
