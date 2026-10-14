import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.jobs.runner import create_job, run_job
from app.models import Company, Draft, Email, JobRun, Person, Signal, SourceSetting, Suppression
from app.services import control, dns_tools, smtp_probe
from app.stages import STAGES
from app.stages import base as stage_base
from tests.conftest import fixture, make_transport

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Delta raises $10M Series A</title><link>https://news.example/delta</link></item></channel></rss>"""
ROUTES = {
    "https://yc-oss.github.io/api/companies/all.json": fixture("yc.json"),
    "https://delta.io/team": fixture("team.html"),
    "https://delta.io/blog": fixture("blog.html"),
    "https://f.example/feed": FEED,
}


def counts(s):
    return [s.scalar(select(func.count()).select_from(m)) for m in (Company, Person, Email, Signal, Draft)]


def run(stage, dry_run=False, source=None, limit=None):
    job_id = create_job(stage, source, limit, dry_run)
    return run_job(job_id), job_id


@pytest.fixture
def configured(session):
    session.add_all([
        SourceSetting(source_name="ycombinator", enabled=True, rate_limit_seconds=1, query_filters={"batch": "W24"}),
        SourceSetting(source_name="press_rss", enabled=True, rate_limit_seconds=1, query_filters={"feeds": ["https://f.example/feed"]}),
    ])
    session.commit()
    stage_base.HTTP_TRANSPORT = make_transport(ROUTES)


def test_full_pipeline(session, configured, monkeypatch):
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: True)
    for stage in ("discover", "find_contacts", "verify_email", "enrich", "draft"):
        status, _ = run(stage)
        assert status == "succeeded", stage
    co = session.scalar(select(Company))
    assert co.domain == "delta.io" and co.normalized_name == "delta" and co.is_hiring
    people = {p.full_name: p for p in session.scalars(select(Person))}
    assert people["Jane Founder"].role_type == "founder" and people["Raj Patel"].role_type == "recruiter"
    jane = people["Jane Founder"].emails
    assert [(e.address, e.confidence, e.status) for e in jane] == [("jane@acme.com", 90, "verified")]
    raj = people["Raj Patel"].emails
    assert len(raj) == 5 and all(e.confidence == 30 and e.status == "unverified" for e in raj)
    types = {s.type for s in session.scalars(select(Signal))}
    assert {"funding", "post"} <= types
    drafts = list(session.scalars(select(Draft)))
    assert len(drafts) == 1 and drafts[0].status == "pending" and drafts[0].llm_provider == "template"
    assert drafts[0].person_id == people["Jane Founder"].id and drafts[0].signals_used
    # idempotent: re-running discover updates instead of duplicating
    run("discover")
    assert session.scalar(select(func.count()).select_from(Company)) == 1


def test_dry_run_changes_nothing_but_reports(session, configured):
    before = counts(session)
    status, job_id = run("discover", dry_run=True)
    session.expire_all()
    assert status == "succeeded" and counts(session) == before
    job = session.get(JobRun, job_id)
    assert job.dry_run and job.stats["dry_run_report"]["would_change"]["companies_created"] == 1


def test_suppression_blocks_email_and_draft(session, configured, monkeypatch):
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: True)
    session.add(Suppression(email_or_domain="acme.com", reason="test"))
    session.commit()
    for stage in ("discover", "find_contacts", "verify_email", "enrich", "draft"):
        run(stage)
    session.expire_all()
    assert not any(e.address.endswith("@acme.com") for e in session.scalars(select(Email)))
    assert session.scalar(select(func.count()).select_from(Draft)) == 0


def test_mx_invalid_domain_stores_no_candidates(session, configured, monkeypatch):
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: False)
    for stage in ("discover", "find_contacts", "verify_email"):
        run(stage)
    emails = list(session.scalars(select(Email)))
    assert [e.address for e in emails] == ["jane@acme.com"]  # only the page-published address


def _probe_setup(monkeypatch, results):
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: True)
    monkeypatch.setattr(smtp_probe, "probe_allowed", lambda d: True)
    calls = []

    def fake(addr):
        calls.append(addr)
        return results(addr)
    monkeypatch.setattr(smtp_probe, "check_address", fake)
    return calls


def test_smtp_valid_marks_verified_and_stops(session, configured, monkeypatch):
    calls = _probe_setup(monkeypatch, lambda a: "valid" if a.startswith("raj@") else "invalid")
    for stage in ("discover", "find_contacts", "verify_email"):
        run(stage)
    raj = session.scalar(select(Person).where(Person.full_name == "Raj Patel"))
    assert [(e.address, e.confidence, e.smtp_status, e.status) for e in raj.emails] == [("raj@delta.io", 80, "valid", "verified")]
    assert "raj.patel@delta.io" in calls and "raj_patel@delta.io" not in calls


def test_catch_all_never_verified(session, configured, monkeypatch):
    calls = _probe_setup(monkeypatch, lambda a: "catch_all")
    for stage in ("discover", "find_contacts", "verify_email"):
        run(stage)
    for name in ("Raj Patel", "Sam Builder"):
        (e,) = session.scalar(select(Person).where(Person.full_name == name)).emails
        assert (e.confidence, e.smtp_status, e.status) == (40, "catch_all", "unverified")
    assert len(calls) == 1  # catch-all domain is remembered, not re-probed


def test_probe_disabled_by_default_in_dry_run(session, configured, monkeypatch):
    calls = _probe_setup(monkeypatch, lambda a: "valid")
    run("discover")
    run("find_contacts")
    run("verify_email", dry_run=True)
    assert calls == []


def test_draft_falls_back_when_ollama_unreachable(session, configured, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(get_settings(), "OLLAMA_URL", "http://127.0.0.1:1")
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: True)
    for stage in ("discover", "find_contacts", "verify_email", "enrich"):
        run(stage)
    status, job_id = run("draft")
    session.expire_all()
    assert status == "succeeded"
    assert session.scalar(select(Draft)).llm_provider == "template"
    assert any("falling back" in w for w in session.get(JobRun, job_id).stats["warnings"])


def test_cancel_stops_within_one_item(session, monkeypatch):
    def slow(ctx):
        for i in range(10):
            ctx.check()
            ctx.count("items")
            if i == 1:
                control.request_cancel(SessionLocal(), ctx.job_id)
    monkeypatch.setitem(STAGES, "discover", slow)
    status, job_id = run("discover")
    session.expire_all()
    job = session.get(JobRun, job_id)
    assert status == "cancelled" and job.stats["counts"]["items"] == 2


def test_kill_switch_stops_running_and_blocks_queued(session, monkeypatch):
    def stage(ctx):
        for i in range(10):
            ctx.check()
            ctx.count("items")
            if i == 2:
                control.set_setting(SessionLocal(), "kill_switch", True)
    monkeypatch.setitem(STAGES, "discover", stage)
    status, job_id = run("discover")
    assert status == "cancelled"
    status2, job2 = run("discover")  # queued job is not picked up while the switch is on
    session.expire_all()
    assert status2 == "cancelled" and "kill switch" in session.get(JobRun, job2).error


def test_failed_stage_records_error(session, monkeypatch):
    def boom(ctx):
        raise RuntimeError("kaput")
    monkeypatch.setitem(STAGES, "discover", boom)
    status, job_id = run("discover")
    session.expire_all()
    job = session.get(JobRun, job_id)
    assert status == "failed" and "kaput" in job.error


def test_threaded_runner_picks_up_queued_job(session, monkeypatch):
    import time

    from app.jobs import threaded

    monkeypatch.setitem(STAGES, "discover", lambda ctx: ctx.count("items"))
    stale = create_job("discover", None, None, True)
    session.get(JobRun, stale).status = "running"  # left behind by a killed process
    session.commit()
    jid = create_job("discover", None, None, True)
    threaded.start()
    try:
        for _ in range(100):
            session.expire_all()
            if session.get(JobRun, jid).status == "succeeded":
                break
            time.sleep(0.1)
    finally:
        threaded.stop()
    assert session.get(JobRun, jid).status == "succeeded" and session.get(JobRun, stale).status == "failed"


def test_rank_and_draft_use_intent_and_guessed_addresses(session, configured, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: True)
    monkeypatch.setattr(get_settings(), "DRAFT_MIN_CONFIDENCE", 30)
    for stage in ("discover", "find_contacts", "verify_email", "enrich", "rank", "draft"):
        assert run(stage)[0] == "succeeded", stage
    people = list(session.scalars(select(Person).order_by(Person.score.desc())))
    assert all(p.intent in ("hire", "invest", "advise") and p.reason for p in people)
    assert session.scalar(select(func.count()).select_from(Draft)) >= 2  # guessed addresses draft too when allowed


def test_discover_limit_counts_new_companies(session, configured):
    run("discover", limit=1)
    assert session.scalar(select(func.count()).select_from(Company)) == 1


def test_stages_do_not_repeat_work(session, configured, monkeypatch):
    monkeypatch.setattr(dns_tools, "has_mx", lambda d: True)
    for stage in ("discover", "find_contacts", "verify_email", "enrich"):
        run(stage)
    n = counts(session)
    _, jid = run("find_contacts")
    run("verify_email")
    run("enrich")
    session.expire_all()
    assert counts(session) == n and session.get(JobRun, jid).stats["progress"]["total"] == 0
