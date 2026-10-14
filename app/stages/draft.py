from sqlalchemy import select

from app.core.config import get_settings
from app.models import Draft, Person, Signal
from app.services.llm import get_provider
from app.services.llm.base import PROMPT_VERSION, DraftInput, LLMError
from app.services.llm.template import TemplateProvider
from app.services.profile import load_profile
from app.stages.base import StageContext


def run(ctx: StageContext) -> None:
    profile = load_profile()
    provider = get_provider()
    template = TemplateProvider()
    if not provider.available():
        ctx.log("warn", f"{provider.name} unreachable; falling back to template provider")
        provider = template
    supp = ctx.suppressed()
    min_conf, min_score = get_settings().DRAFT_MIN_CONFIDENCE, get_settings().DRAFT_MIN_SCORE
    drafted = {p for (p,) in ctx.session.execute(select(Draft.person_id))}
    people = list(ctx.session.scalars(select(Person).order_by(Person.score.desc(), Person.id)))  # best matches first
    todo = []
    for p in people:
        if p.id in drafted:
            continue
        ok = [e for e in p.emails if (e.status == "verified" or e.confidence >= min_conf) and e.address not in supp]
        if p.score < min_score:
            continue
        if not ok:
            continue
        sigs = list(ctx.session.scalars(
            select(Signal).where(Signal.company_id == p.company_id).order_by(Signal.observed_at.desc().nulls_last()).limit(3)
        ))
        if sigs:
            todo.append((p, sigs))
    todo = todo[: ctx.limit] if ctx.limit else todo
    errors = 0
    for i, (p, sigs) in enumerate(todo, 1):
        ctx.check()
        pref = {"hire": "hiring", "invest": "funding"}.get(p.intent or "", "")
        sigs = sorted(sigs, key=lambda s: s.type != pref)  # lead with the signal that fits the goal
        used = [{"type": s.type, "value": s.value, "url": s.url} for s in sigs]
        text = f"{p.company.description or ''} {p.company.industry or ''}"
        inp = DraftInput(profile, p.full_name, p.title, p.role_type, p.company.name, used, p.intent or "hire", text)
        used_provider = provider
        try:
            out = provider.draft(inp)
        except LLMError as e:
            ctx.log("warn", f"{provider.name} failed for person {p.id} ({e}); using template")
            out, used_provider = template.draft(inp), template
        ctx.session.add(Draft(
            person_id=p.id, company_id=p.company_id, subject=out["subject"], body=out["body"],
            prompt_version=PROMPT_VERSION, llm_provider=used_provider.name, signals_used=used, status="pending",
        ))
        ctx.count("drafts_created")
        ctx.progress(i, len(todo), errors)
