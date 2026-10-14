import pytest

from app.models import Company, Draft, Email, Person, Suppression
from app.sender import can_send, send
from app.services.cron import validate_cron
from app.services.llm.base import DraftInput, LLMError, parse_draft_json
from app.services.llm.template import TemplateProvider
from app.services.normalize import (
    candidate_emails,
    classify_role,
    confidence,
    domain_of,
    name_slug,
    normalize_name,
)


def test_normalize_name():
    assert normalize_name("Acme Robotics Pvt. Ltd.") == "acme robotics"
    assert normalize_name("Delta, Inc.") == "delta"
    assert name_slug("Foo Bar LLC") == "foobar"


def test_domain_of():
    assert domain_of("https://www.Delta.io/path?x=1") == "delta.io"
    assert domain_of("delta.io") == "delta.io"
    assert domain_of(None) is None and domain_of("localhost") is None


def test_candidate_patterns():
    got = dict((p, a) for a, p in candidate_emails("Jane Q. Founder", "acme.com"))
    assert got["first.last"] == "jane.founder@acme.com"
    assert got["flast"] == "jfounder@acme.com"
    assert len(got) == 5
    assert candidate_emails("Cher", "acme.com") == []


@pytest.mark.parametrize("title,role", [
    ("Co-Founder & CEO", "founder"), ("CTO", "founder"), ("Head of Talent", "recruiter"),
    ("People Ops Lead", "recruiter"), ("VP Engineering", "exec"), ("Director of Sales", "exec"),
    ("Software Engineer", "other"), (None, "other"),
])
def test_classify_role(title, role):
    assert classify_role(title) == role


def test_confidence_scores():
    assert confidence("direct", "") == 90
    assert [confidence("generated", s) for s in ("valid", "catch_all", "not_checked", "unknown")] == [80, 40, 30, 10]


@pytest.mark.parametrize("expr,ok", [
    ("0 * * * *", True), ("0 6 * * 1", True), ("*/15 * * * *", True),
    ("*/5 * * * *", False), ("* * * * *", False), ("0,10 * * * *", False), ("nonsense", False),
])
def test_cron_validation(expr, ok):
    if ok:
        validate_cron(expr)
    else:
        with pytest.raises(ValueError):
            validate_cron(expr)


def test_can_send_rules(session):
    co = Company(name="A", normalized_name="a", extra={})
    session.add(co)
    session.flush()
    p = Person(company_id=co.id, full_name="X Y", extra={})
    session.add(p)
    session.flush()
    session.add_all([
        Email(person_id=p.id, address="ok@a.com", status="verified", confidence=90),
        Email(person_id=p.id, address="unv@a.com", status="unverified"),
        Email(person_id=p.id, address="bounced@a.com", status="bounced"),
        Email(person_id=p.id, address="opt@a.com", status="opted_out"),
        Email(person_id=p.id, address="supp@b.com", status="verified"),
    ])
    session.add(Suppression(email_or_domain="b.com"))
    session.commit()
    assert can_send(session, "ok@a.com")
    assert not any(can_send(session, a) for a in ("unv@a.com", "bounced@a.com", "opt@a.com", "supp@b.com", "none@a.com"))


def test_can_send_daily_cap(session):
    co = Company(name="A", normalized_name="a", extra={})
    session.add(co)
    session.flush()
    p = Person(company_id=co.id, full_name="X Y", extra={})
    session.add(p)
    session.flush()
    session.add(Email(person_id=p.id, address="ok@a.com", status="verified"))
    from app.models import now
    from app.services.control import set_setting
    set_setting(session, "daily_send_cap", 1)
    session.add(Draft(person_id=p.id, company_id=co.id, subject="s", body="b", prompt_version="v1",
                      llm_provider="t", status="sent", reviewed_at=now()))
    session.commit()
    assert not can_send(session, "ok@a.com")


def test_send_is_stub():
    with pytest.raises(NotImplementedError):
        send("a@b.com", "s", "b")


def test_parse_draft_json_strips_fences():
    d = parse_draft_json('```json\n{"subject": "Hi", "body": "Text"}\n```')
    assert d == {"subject": "Hi", "body": "Text"}
    for bad in ("not json", '{"subject": 1, "body": "x"}', "[]"):
        with pytest.raises(LLMError):
            parse_draft_json(bad)


def test_template_draft_is_valid():
    import yaml

    from tests.conftest import FIX
    profile = yaml.safe_load((FIX / "profile.yaml").read_text())
    inp = DraftInput(profile, "Jane Founder", "CEO", "founder", "Acme Robotics",
                     [{"type": "funding", "value": "Acme Robotics raises $5M seed round", "url": "u"}])
    d = TemplateProvider().draft(inp)
    assert 60 <= len(d["body"].split()) <= 170  # templates are not held to the LLM 80-120 word rule
    assert "Acme Robotics" in d["body"] and "Jane" in d["body"]


def test_investor_role():
    assert classify_role("General Partner") == "investor"
    assert classify_role("Angel Investor") == "investor"
    assert classify_role("Partner Manager") == "other"


def test_relevance_scoring_and_intent():
    from types import SimpleNamespace as NS

    from app.services.relevance import score_person
    prof = {"skills": ["React", "TypeScript"], "target_roles": ["Frontend Developer"], "projects": [{"tags": ["fintech", "trading"]}]}
    co = NS(name="Acme", is_hiring=True, description="A fintech trading platform", industry="Fintech", extra={})
    hire = [NS(type="hiring", value="4 open roles, including Frontend Engineer (React)")]
    score, intent, why = score_person("founder", co, hire, prof, 30)
    assert intent == "hire" and score >= 65 and "react" in why
    s2, i2, _ = score_person("recruiter", co, [], prof, 0)
    assert i2 == "hire" and s2 < score
    vc = NS(name="VC", is_hiring=False, description="", industry="", extra={"kind": "investor"})
    assert score_person("investor", vc, [], prof, 0)[1] == "invest"
    plain = NS(name="X", is_hiring=False, description="", industry="", extra={})
    assert score_person("other", plain, [], prof, 0)[1] == "advise"


@pytest.mark.parametrize("intent", ["hire", "invest", "advise"])
def test_templates_valid_for_each_intent(intent):
    import yaml

    from tests.conftest import FIX
    profile = yaml.safe_load((FIX / "profile.yaml").read_text())
    inp = DraftInput(profile, "Jane Founder", "CEO", "founder", "Acme Robotics",
                     [{"type": "funding", "value": "Acme Robotics raises $5M seed round", "url": "u"}], intent, "robotics")
    body = TemplateProvider().draft(inp)["body"]
    assert 60 <= len(body.split()) <= 170 and "opt out" not in body and "P.S." not in body


@pytest.mark.parametrize("name,ok", [
    ("Jane Founder", True), ("Aleem Mawani", True), ("Wei-Wei Wu", True), ("Ka Ling Wu", True),
    ("AI Recruiting Platform", False), ("Talent Match", False), ("Explore Resume Screens", False), ("Chief Executive Officer", False),
    ("Startup Directory", False), ("Hiring Managers", False), ("Compare Alex", False), ("Madonna", False),
])
def test_is_person_name(name, ok):
    from app.services.normalize import is_person_name
    assert is_person_name(name) is ok


def test_title_other_org():
    from app.services.normalize import title_other_org
    assert title_other_org("CEO, Tier4 Group", "Alex")
    assert title_other_org("Senior Design Director, Code and Theory", "Figma")
    assert not title_other_org("SVP, Chief Customer Officer", "Amplitude")
    assert not title_other_org("Co-founder & CEO of Sonia Health", "Sonia")
    assert not title_other_org("CEO, Tier4 Group", "Tier4 Group")


def test_advise_body_has_why_and_concrete_question():
    import yaml

    from tests.conftest import FIX
    profile = yaml.safe_load((FIX / "profile.yaml").read_text())
    inp = DraftInput(profile, "Aleem Mawani", "CEO", "founder", "Streak", [{"type": "hiring", "value": "Job: Frontend (Remote)", "url": None}],
                     "advise", "Email-based CRM for Gmail", "crm gmail")
    body = TemplateProvider().draft(inp)["body"]
    assert "I have been following Streak: Email-based CRM for Gmail." in body and "what is the first thing you would improve" in body


def test_both_featured_projects_with_live_links_in_every_email():
    prof = {"name": "S G", "role": "Dev", "location": "Delhi", "skills": ["React"], "target_roles": ["Frontend Developer"],
            "projects": [{"name": "Orbit", "description": "trading tool", "link": "https://g/orbit", "demo": "https://orbit.live", "featured": True},
                         {"name": "Dentiq", "description": "clinic CRM", "link": "https://g/dentiq", "demo": "https://dentiq.live", "featured": True},
                         {"name": "Hidden", "description": "x", "link": "https://g/hidden", "demo": "https://hidden.live"}]}
    for intent in ("hire", "invest", "advise"):
        body = TemplateProvider().draft(DraftInput(prof, "Ann Lee", "CEO", "founder", "Acme", [], intent, "a company"))["body"]
        for url in ("https://orbit.live", "https://dentiq.live", "https://g/orbit", "https://g/dentiq"):
            assert url in body, (intent, url)
        assert "Hidden" not in body and "hidden.live" not in body
    for kind in ("followup", "final"):
        body = TemplateProvider().followup(kind, DraftInput(prof, "Ann Lee", "CEO", "founder", "Acme", [], "advise", ""))
        assert "https://orbit.live" in body and "https://dentiq.live" in body and "Hidden" not in body
