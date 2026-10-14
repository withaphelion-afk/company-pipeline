import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.jobs.runner import create_job, run_job
from app.main import app
from app.models import Company, Draft, Email, Person, Signal
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
