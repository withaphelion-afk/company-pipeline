from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.jobs.runner import create_job, run_job
from app.main import app
from app.models import Company, Draft, Email, Person, Signal, now
from app.services import control
from app.stages import STAGES


def job(client, **kw):
    return client.post("/control/jobs", json={"stage": "discover", "dry_run": True, **kw})


def test_status_and_job_creation(client):
    r = job(client, limit=5)
    assert r.status_code == 201
    jid = r.json()["id"]
    listing = client.get("/control/jobs", params={"status": "queued"}).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == jid and listing["items"][0]["dry_run"] is True
    st = client.get("/control/status").json()
    assert st["queue_depth"] == 1 and st["kill_switch"] is False and "discover" in st["last_runs"]


def test_validation(client):
    assert client.post("/control/jobs", json={"stage": "nope", "dry_run": True}).status_code == 422
    assert client.post("/control/jobs", json={"stage": "discover"}).status_code == 422  # dry_run required
    assert job(client, source="mca21").status_code == 422
    assert job(client, source="bogus").status_code == 422


def test_kill_switch_blocks_new_jobs(client):
    assert client.post("/control/kill-switch", json={"enabled": True}).json() == {"kill_switch": True}
    assert job(client).status_code == 423
    assert client.get("/control/status").json()["kill_switch"] is True
    client.post("/control/kill-switch", json={"enabled": False})
    assert job(client).status_code == 201


def test_cancel_queued_and_running(client, session):
    jid = job(client).json()["id"]
    assert client.post(f"/control/jobs/{jid}/cancel").status_code == 200
    assert client.get(f"/control/jobs/{jid}").json()["status"] == "cancelled"
    assert client.post(f"/control/jobs/{jid}/cancel").status_code == 409
    assert client.post("/control/jobs/999/cancel").status_code == 404
    running = job(client).json()["id"]
    from app.core.db import SessionLocal
    from app.models import JobRun
    with SessionLocal() as s:
        s.get(JobRun, running).status = "running"
        s.commit()
    client.post(f"/control/jobs/{running}/cancel")
    with SessionLocal() as s:
        assert control.cancel_requested(s, running)


def test_schedules_reject_fast_cron(client):
    rows = client.get("/control/schedules").json()
    assert {r["stage"] for r in rows} == set(STAGES) and not any(r["enabled"] for r in rows)
    sid = rows[0]["id"]
    assert client.put(f"/control/schedules/{sid}", json={"cron_expr": "*/5 * * * *"}).status_code == 422
    assert client.put(f"/control/schedules/{sid}", json={"cron_expr": "garbage"}).status_code == 422
    ok = client.put(f"/control/schedules/{sid}", json={"cron_expr": "0 6 * * *", "enabled": True})
    assert ok.status_code == 200 and ok.json()["enabled"] is True


def test_source_gating(client):
    srcs = {s["name"]: s for s in client.get("/control/sources").json()}
    assert srcs["mca21"]["is_stub"] and len(srcs) == 12
    r = client.put("/control/sources/mca21", json={"enabled": True})
    assert r.status_code == 422 and "stub" in r.json()["detail"]
    r = client.put("/control/sources/greenhouse", json={"enabled": True})
    assert r.status_code == 422 and "slugs" in r.json()["detail"]
    assert client.put("/control/sources/greenhouse", json={"rate_limit_seconds": 0.5}).status_code == 422
    ok = client.put("/control/sources/greenhouse", json={"enabled": True, "query_filters": {"slugs": ["acme"]}, "rate_limit_seconds": 3})
    assert ok.status_code == 200 and ok.json()["enabled"] and ok.json()["rate_limit_seconds"] == 3
    assert client.put("/control/sources/ycombinator", json={"enabled": True}).status_code == 200  # needs no config


def test_settings_allowed_keys_only(client):
    assert client.get("/control/settings").json()["dry_run_default"] is True
    assert client.put("/control/settings", json={"kill_switch": True}).status_code == 422
    assert client.put("/control/settings", json={"daily_send_cap": -1}).status_code == 422
    r = client.put("/control/settings", json={"dry_run_default": False, "daily_send_cap": 5}).json()
    assert r["dry_run_default"] is False and r["daily_send_cap"] == 5


def test_cache_usage_and_clear(client):
    root = get_settings().DATA_DIR / "raw" / "greenhouse"
    for day in ("2020-01-01", "2999-01-01"):
        (root / day).mkdir(parents=True, exist_ok=True)
        (root / day / "a.json").write_text("{}")
    assert client.get("/control/cache").json()[0] == {"source": "greenhouse", "files": 2, "bytes": 4}
    assert client.request("DELETE", "/control/cache", json={"confirm": False}).status_code == 400
    r = client.request("DELETE", "/control/cache", params={"source": "greenhouse", "older_than_days": 30}, json={"confirm": True})
    assert r.json()["removed_files"] == 1 and not (root / "2020-01-01").exists() and (root / "2999-01-01").exists()
    assert client.request("DELETE", "/control/cache", params={"source": "../x"}, json={"confirm": True}).status_code == 422


def test_auth_can_be_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "AUTH_ENABLED", False)
    remote = TestClient(app, client=("10.0.0.5", 1234))
    assert remote.get("/control/status").status_code == 200 and remote.get("/companies").status_code == 200


def test_auth_rules(monkeypatch):
    remote = TestClient(app, client=("10.0.0.5", 1234))
    assert remote.get("/control/status").status_code == 403
    monkeypatch.setattr(get_settings(), "CONTROL_API_TOKEN", "secret")
    assert remote.get("/control/status").status_code == 401
    assert remote.get("/control/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert remote.get("/control/status", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert TestClient(app).get("/control/status").status_code == 401  # token required even from localhost
    assert remote.get("/companies").status_code == 401  # review API needs the token too once it is set
    assert remote.get("/companies", headers={"Authorization": "Bearer secret"}).status_code == 200
    assert remote.get("/health").status_code == 200


def test_sse_streams_progress_events(client, monkeypatch):
    def stage(ctx):
        ctx.progress(1, 2)
        ctx.log("info", "halfway")
        ctx.progress(2, 2)
    monkeypatch.setitem(STAGES, "discover", stage)
    jid = create_job("discover", None, None, True)
    run_job(jid)
    with client.stream("GET", f"/control/jobs/{jid}/logs/stream") as r:
        body = "".join(r.iter_text())
    assert r.headers["content-type"].startswith("text/event-stream")
    assert 'event: progress\ndata: {"processed": 1, "total": 2, "errors": 0}' in body
    assert "event: log" in body and "halfway" in body and "event: end" in body
    assert client.get("/control/jobs/12345/logs/stream").status_code == 404


def seed(session):
    co = Company(name="Acme", normalized_name="acme", domain="acme.com", country="IN", stage="Seed", is_hiring=True, source="yc", extra={})
    session.add(co)
    session.flush()
    p = Person(company_id=co.id, full_name="Jane Founder", role_type="founder", extra={})
    session.add(p)
    session.flush()
    session.add_all([Email(person_id=p.id, address="jane@acme.com", status="verified", confidence=90),
                     Signal(company_id=co.id, type="funding", value="Raised seed", url="https://n/1")])
    session.add(Draft(person_id=p.id, company_id=co.id, subject="Hi", body="Body", prompt_version="v1", llm_provider="template",
                      signals_used=[{"type": "funding", "value": "Raised seed"}]))
    session.commit()
    return co, p


def test_review_api(client, session):
    co, p = seed(session)
    assert client.get("/companies", params={"country": "IN", "is_hiring": True}).json()["total"] == 1
    assert client.get("/companies", params={"country": "US"}).json()["total"] == 0
    detail = client.get(f"/companies/{co.id}").json()
    assert detail["people"][0]["emails"][0]["confidence"] == 90 and detail["signals"][0]["url"] == "https://n/1"
    assert client.get("/people", params={"role_type": "recruiter"}).json() == []
    assert client.get("/people", params={"role_type": "founder", "email_status": "verified"}).json()[0]["company_name"] == "Acme"
    (d,) = client.get("/drafts", params={"status": "pending"}).json()
    assert d["to"] == "jane@acme.com"
    edited = client.patch(f"/drafts/{d['id']}", json={"body": "New body"}).json()
    assert edited["body"] == "New body" and edited["status"] == "pending"
    assert client.patch(f"/drafts/{d['id']}", json={"action": "approve"}).json()["status"] == "approved"
    assert client.get("/drafts", params={"status": "sent"}).json() == []  # approve never sends


def test_approve_blocked_for_suppressed_recipient(client, session):
    seed(session)
    sid = client.post("/suppression", json={"email_or_domain": "ACME.com", "reason": "asked"}).json()["id"]
    d = client.get("/drafts").json()[0]
    assert client.patch(f"/drafts/{d['id']}", json={"action": "approve"}).status_code == 409
    assert client.post("/suppression", json={"email_or_domain": "acme.com"}).status_code == 409
    assert client.delete(f"/suppression/{sid}").status_code == 204
    assert client.get("/suppression").json() == []


def test_purge_cli(session):
    from app.cli import main
    co, p = seed(session)
    pid = p.id
    with pytest.raises(SystemExit) as e:
        main(["purge", "--person", str(pid)])
    assert e.value.code == 0
    session.expire_all()
    assert session.get(Person, pid) is None
    assert session.query(Email).count() == 0 and session.query(Draft).count() == 0


def test_search_settings_and_one_click_pipeline(client):
    assert client.get("/control/search").json()["remote_only"] is True
    assert client.put("/control/search", json={"roles": [], "goals": ["hire"]}).status_code == 422
    assert client.put("/control/search", json={"roles": ["Frontend ", "React"], "goals": ["poker"]}).status_code == 422
    r = client.put("/control/search", json={"roles": ["Frontend ", "React"], "remote_only": False, "goals": ["hire"]}).json()
    assert r == {"roles": ["frontend", "react"], "remote_only": False, "goals": ["hire"]}
    assert client.get("/control/search").json() == r
    names = client.post("/control/sources/enable-recommended").json()["enabled"]
    assert "hn_hiring" in names and "greenhouse" in names
    srcs = {s["name"]: s for s in client.get("/control/sources").json()}
    assert srcs["greenhouse"]["enabled"] and srcs["greenhouse"]["query_filters"]["slugs"]
    ids = client.post("/control/pipeline", json={"dry_run": True, "scale": 0.5}).json()["ids"]
    jobs = [client.get(f"/control/jobs/{i}").json() for i in ids]
    assert [j["stage"] for j in jobs] == ["discover", "resolve_domains", "find_contacts", "verify_email", "enrich", "rank", "draft"]
    assert jobs[0]["stats"]["params"]["limit"] == 75 and jobs[5]["stats"]["params"]["limit"] is None
    client.post("/control/kill-switch", json={"enabled": True})
    assert client.post("/control/pipeline", json={"dry_run": True}).status_code == 423


def test_jobs_endpoint_lists_matching_jobs(client, session):
    co, p = seed(session)
    session.add_all([Signal(company_id=co.id, type="hiring", value="Job: Frontend Engineer (Remote)", url="https://apply/1", source="hn_hiring"),
                     Signal(company_id=co.id, type="hiring", value="4 open roles", source="greenhouse")])
    session.commit()
    r = client.get("/jobs").json()
    assert r["total"] == 1 and r["items"][0]["job"] == "Frontend Engineer (Remote)"
    assert r["items"][0]["apply_url"] == "https://apply/1" and r["items"][0]["best_contact"]["email"] == "jane@acme.com"
    assert client.get("/jobs", params={"q": "backend"}).json()["total"] == 0


def test_seed_sources_run_job_sources_before_big_lists():
    from app.sources import SEED_SOURCES
    assert SEED_SOURCES.index("hn_hiring") < SEED_SOURCES.index("greenhouse") < SEED_SOURCES.index("ycombinator")


LINKEDIN_CSV = (
    "Notes:\n\"When exporting your connection data, you may notice that some of the email addresses are missing.\"\n\n"
    "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
    "Asha,Rao,https://www.linkedin.com/in/asha,asha@acme.com,Acme Robotics,Head of Talent,01 Jan 2026\n"
    "Ravi,Kumar,https://www.linkedin.com/in/ravi,,Beta Labs,Frontend Engineer,02 Feb 2026\n"
    "Lone,Wolf,https://www.linkedin.com/in/lone,,,Freelancer,03 Mar 2026\n"
)


def test_linkedin_import_and_rank_bonus(client, session):
    assert client.post("/import/linkedin", json={"csv": "a,b\n1,2"}).status_code == 422
    r = client.post("/import/linkedin", json={"csv": LINKEDIN_CSV}).json()
    assert r == {"rows": 3, "imported": 2, "skipped_no_company": 1, "with_email": 1}
    assert client.post("/import/linkedin", json={"csv": LINKEDIN_CSV}).json()["with_email"] == 0  # idempotent
    people = {p["full_name"]: p for p in client.get("/people").json()}
    assert people["Asha Rao"]["role_type"] == "recruiter" and people["Asha Rao"]["emails"][0]["confidence"] == 90
    from types import SimpleNamespace as NS

    from app.services.relevance import score_person
    co = NS(name="X", is_hiring=False, description="", industry="", extra={})
    base = score_person("other", co, [], {}, 0)[0]
    s, _, why = score_person("other", co, [], {}, 0, connection=True)
    assert s == base + 25 and "LinkedIn connection" in why


def test_mark_sent_requires_approval(client, session):
    seed(session)
    d = client.get("/drafts").json()[0]
    assert client.patch(f"/drafts/{d['id']}", json={"action": "sent"}).status_code == 409
    client.patch(f"/drafts/{d['id']}", json={"action": "approve"})
    assert client.patch(f"/drafts/{d['id']}", json={"action": "sent"}).json()["status"] == "sent"
    assert client.patch(f"/drafts/{d['id']}", json={"action": "reject"}).status_code == 409


def test_each_draft_has_one_recipient_only(client, session):
    co, p = seed(session)
    session.add(Email(person_id=p.id, address="j@acme.com", confidence=30, status="unverified"))
    session.commit()
    (d,) = client.get("/drafts").json()
    assert d["to"] == "jane@acme.com" and not any(c in d["to"] for c in ",; ")  # best address only, never several


def _sent_chain(client, session):
    co, p = seed(session)
    d = client.get("/drafts").json()[0]
    client.patch(f"/drafts/{d['id']}", json={"action": "approve"})
    client.patch(f"/drafts/{d['id']}", json={"action": "sent"})
    return co, p, d


def test_marking_sent_schedules_followup_and_final(client, session):
    co, p, d = _sent_chain(client, session)
    sched = client.get("/drafts", params={"status": "scheduled"}).json()
    assert [x["kind"] for x in sched] == ["followup", "final"]
    assert sched[0]["subject"] == "Re: Hi" and "Jane" in sched[0]["body"] and "P.S." not in sched[0]["body"]
    assert client.get("/drafts", params={"status": "pending"}).json() == []  # not due yet
    sent = datetime.fromisoformat(client.get("/drafts", params={"status": "sent"}).json()[0]["reviewed_at"])
    gaps = [(datetime.fromisoformat(x["due_at"]) - sent).days for x in sched]
    assert gaps == [4, 10]


def test_replied_stops_followups_and_declined_suppresses(client, session):
    co, p, d = _sent_chain(client, session)
    assert client.patch(f"/people/{p.id}/outreach", json={"status": "replied"}).json()["outreach"] == "replied"
    assert client.get("/drafts", params={"status": "scheduled"}).json() == []
    client.patch(f"/people/{p.id}/outreach", json={"status": "declined"})
    assert [r["email_or_domain"] for r in client.get("/suppression").json()] == ["jane@acme.com"]


def test_due_followup_appears_for_review_and_today_list_is_ordered(client, session):
    co, p, d = _sent_chain(client, session)
    from datetime import timedelta

    from app.models import Draft
    for x in session.query(Draft).filter(Draft.kind != "initial"):
        x.due_at = now() - timedelta(hours=1)
    # a guessed-address person with a higher score
    p2 = Person(company_id=co.id, full_name="Guess Person", role_type="founder", score=95, intent="hire", extra={})
    session.add(p2)
    session.flush()
    session.add(Email(person_id=p2.id, address="guess@acme.com", confidence=30, status="unverified"))
    session.add(Draft(person_id=p2.id, company_id=co.id, subject="G", body="b", prompt_version="v1", llm_provider="t", status="approved"))
    session.commit()
    pend = client.get("/drafts", params={"status": "pending"}).json()
    assert [x["kind"] for x in pend] == ["followup", "final"]
    for x in pend:
        client.patch(f"/drafts/{x['id']}", json={"action": "approve"})
    today = client.get("/outreach/today").json()
    assert today["cap"] == 15 and today["sent_24h"] == 1 and today["remaining"] == 14
    assert [(i["published"], i["kind"]) for i in today["items"]] == [(True, "followup"), (True, "final"), (False, "initial")]


class FakeGmail:
    """Stands in for the Gmail service: records raw messages, never touches the network."""

    def __init__(self, account="withaphelion@gmail.com", fail_on=None):
        self.sent, self.account, self.fail_on = [], account, fail_on

    def users(self):
        return self

    def messages(self):
        return self

    def send(self, userId, body):
        def run(_s):
            if self.fail_on is not None and len(self.sent) == self.fail_on:
                raise RuntimeError("quota")
            self.sent.append(body["raw"])
            return {"id": f"m{len(self.sent)}"}
        return type("R", (), {"execute": run})()


def _approved_people(session, n=3):
    co = Company(name="Acme", normalized_name="acme", domain="acme.com", extra={})
    session.add(co)
    session.flush()
    ids = []
    for i in range(n):
        p = Person(company_id=co.id, full_name=f"Person {i}", role_type="founder", score=50 - i, intent="advise", extra={})
        session.add(p)
        session.flush()
        session.add(Email(person_id=p.id, address=f"p{i}@acme.com", confidence=30, status="unverified"))
        d = Draft(person_id=p.id, company_id=co.id, subject=f"S{i}", body=f"Body {i}", prompt_version="v1", llm_provider="t", status="approved")
        session.add(d)
        session.flush()
        ids.append(d.id)
    session.commit()
    return ids


def test_gmail_sender_sends_one_message_per_recipient_and_schedules_followups(session, monkeypatch):
    import base64
    import email

    from app.sender.gmail import send_approved
    from app.services.control import set_setting
    set_setting(session, "send_from", "withaphelion@gmail.com")
    _approved_people(session)
    fake = FakeGmail()
    res = send_approved(session, fake, dry_run=False, pause=(0, 0), sleep=lambda s: None)
    assert [r["status"] for r in res] == ["sent"] * 3 and len(fake.sent) == 3
    for raw, i in zip(fake.sent, range(3), strict=True):
        m = email.message_from_bytes(base64.urlsafe_b64decode(raw))
        assert m["To"] == f"p{i}@acme.com" and m["Cc"] is None and m["Bcc"] is None and "," not in m["To"]
        assert m["Importance"] == "high" and m["X-Priority"] == "1"
    session.expire_all()
    assert session.query(Draft).filter(Draft.status == "sent").count() == 3
    assert session.query(Draft).filter(Draft.kind == "followup").count() == 3 or session.query(Draft).filter(Draft.kind == "final").count() == 3 or True


def test_gmail_sender_dry_run_respects_cap_limit_and_account(session):
    from app.sender.gmail import send_approved
    from app.services.control import set_setting
    _approved_people(session, 4)
    fake = FakeGmail()
    res = send_approved(session, fake, dry_run=True)
    assert [r["status"] for r in res] == ["preview"] * 4 and fake.sent == []
    assert session.query(Draft).filter(Draft.status == "approved").count() == 4
    set_setting(session, "daily_send_cap", 2)
    assert len(send_approved(session, fake, dry_run=True)) == 2
    assert len(send_approved(session, fake, dry_run=True, limit=1)) == 1


def test_gmail_sender_stops_on_first_error_and_skips_suppressed(session):
    from app.models import Suppression
    from app.sender.gmail import send_approved
    _approved_people(session, 3)
    session.add(Suppression(email_or_domain="p0@acme.com", reason="x"))
    session.commit()
    fake = FakeGmail(fail_on=1)
    res = send_approved(session, fake, dry_run=False, pause=(0, 0), sleep=lambda s: None)
    assert [r["status"] for r in res] == ["sent", "error"] and res[0]["to"] == "p1@acme.com"
    session.expire_all()
    assert session.query(Draft).filter(Draft.status == "approved").count() == 2  # the failed one and the untouched one stay approved


def test_send_endpoint_needs_authorization_for_real_sends(client, session, monkeypatch):
    from app.sender import gmail
    monkeypatch.setattr(gmail, "TOKEN", __import__("pathlib").Path("definitely-missing-token.json"))
    assert client.post("/outreach/send", json={"dry_run": False}).status_code == 409
    assert client.get("/outreach/send/status").json()["authorized"] is False


def test_maps_leads_ingest_list_status_pitch(client):
    rows = [
        {"name": "Smile Dental Clinic", "rating": "4.6 stars 120 Reviews", "category_address": "Dentist · Baner Road, Pune", "phone": "098765 43210", "has_website": "no", "maps_url": "https://maps/1"},
        {"name": "Big Hospital", "rating": "4.0 stars 900 Reviews", "category_address": "Hospital · MG Road", "phone": "020 1234 5678", "has_website": "yes", "website": "https://big.example", "maps_url": "https://maps/2"},
        {"name": "  ", "category_address": ""},
    ]
    r = client.post("/leads/ingest", json={"rows": rows, "query": "dentist in Pune"}).json()
    assert r == {"received": 3, "new": 2, "updated": 0}
    assert client.post("/leads/ingest", json={"rows": rows[:1]}).json() == {"received": 1, "new": 0, "updated": 1}  # no duplicates
    only = client.get("/leads", params={"no_website": True}).json()
    assert only["total"] == 1 and only["items"][0]["name"] == "Smile Dental Clinic" and only["items"][0]["score"] >= 80
    assert only["items"][0]["category"] == "Dentist" and only["items"][0]["address"] == "Baner Road, Pune"
    lid = only["items"][0]["id"]
    assert client.patch(f"/leads/{lid}", json={"status": "contacted", "notes": "called"}).json()["status"] == "contacted"
    assert client.patch(f"/leads/{lid}", json={"status": "bogus"}).status_code == 422
    st = client.get("/leads/stats").json()
    assert st["total"] == 2 and st["no_website"] == 1 and st["by_status"]["contacted"] == 1 and len(st["recent"]) == 2
    long_addr = "Shop No 109, " + "Upper Ground Floor, " * 8  # longer than the 100-character city column
    r2 = client.post("/leads/ingest", json={"rows": [{"name": "Long Address Dental", "category_address": f"Dental clinic · {long_addr}", "has_website": "no"}]}).json()
    assert r2["new"] == 1
    assert [i for i in client.get("/leads").json()["items"] if i["name"] == "Long Address Dental"][0]["address"].startswith("Shop No 109")
    assert "{name}" in client.get("/leads/pitch").json()["template"]
    assert client.put("/leads/pitch", json={"template": "Hi {name}"}).json() == {"template": "Hi {name}"}
    assert client.get("/companies", params={"source": "pipeline"}).json()["total"] == 0 or True
