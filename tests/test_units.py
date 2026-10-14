import pytest

from app.models import Company, Draft, Email, Person, Suppression
from app.sender import can_send, send
from app.services.cron import validate_cron
from app.services.llm.base import DraftInput, LLMError, parse_draft_json, validate_draft
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
    validate_draft(d)  # 80-120 words, opt-out sentence present
    assert "Acme Robotics" in d["body"] and "Jane" in d["body"]
