from sqlalchemy import select

from app.models import Person, Signal
from app.services.profile import load_profile
from app.services.relevance import score_person
from app.stages.base import StageContext


def run(ctx: StageContext) -> None:
    profile = load_profile()
    people = list(ctx.session.scalars(select(Person).order_by(Person.id).limit(ctx.limit or 100_000)))
    by_company: dict[int, list[Signal]] = {}
    for sg in ctx.session.scalars(select(Signal)):
        by_company.setdefault(sg.company_id, []).append(sg)
    for i, p in enumerate(people, 1):
        ctx.check()
        conf = max((e.confidence for e in p.emails), default=0)
        p.score, p.intent, p.reason = score_person(p.role_type, p.company, by_company.get(p.company_id, []), profile, conf)
        ctx.count(f"intent_{p.intent}")
        if i % 25 == 0 or i == len(people):
            ctx.progress(i, len(people))
