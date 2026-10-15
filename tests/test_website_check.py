import pytest
from sqlalchemy import select

from app.jobs.runner import create_job, run_job
from app.models import Company
from app.services import website_check
from app.services.http_client import HttpClient
from app.services.website_check import (
    classify,
    distinctive_tokens,
    domain_guesses,
    is_aggregator,
    page_matches,
)
from app.stages import base as stage_base
from tests.conftest import make_transport

NAME, PHONE = "Glow Aesthetic Skin Clinic", "011 2345 6789"


def client(routes):
    return HttpClient("website_check", rate_limit=0, transport=make_transport(routes), backoff=0)


@pytest.fixture(autouse=True)
def no_dns(monkeypatch):
    monkeypatch.setattr(website_check, "resolves", lambda host: host == "glow.com")  # only this guess exists


def test_helpers():
    assert is_aggregator("https://www.instagram.com/glow") and is_aggregator("https://g.page/x") is False
    assert is_aggregator("https://justdial.com/Delhi/Glow") and not is_aggregator("https://glowclinic.com")
    assert distinctive_tokens(NAME) == ["glow"]
    assert "glow.com" in domain_guesses(NAME) and "glow.in" in domain_guesses(NAME)
    assert page_matches("<p>Call 011-2345-6789</p>", "Other Name", PHONE) == "phone number"
    assert page_matches("<h1>Welcome to Glow</h1>", NAME, "") == "business name"
    assert page_matches("<h1>Something else</h1>", NAME, PHONE) is None


def test_website_listed_on_maps_is_trusted_without_fetching():
    v = classify(NAME, PHONE, "https://glowskin.in/?utm=1", [], True, client({}))
    assert (v.status, v.url) == ("has_site", "https://glowskin.in") and "Google Maps" in v.evidence


def test_social_only_listing_is_not_a_website():
    v = classify(NAME, PHONE, "https://instagram.com/glow", [], True, client({}))
    assert v.status == "none" and "no website" in v.evidence


def test_link_on_the_listing_that_matches_the_business():
    routes = {"https://glowderma.com": "<title>Glow Aesthetic Skin Clinic Delhi</title>"}
    v = classify(NAME, PHONE, "", ["https://glowderma.com/book?x=1", "https://facebook.com/glow"], True, client(routes))
    assert v.status == "has_site" and v.url == "https://glowderma.com" and "link on the listing" in v.evidence


def test_listing_link_that_cannot_be_matched_is_probable_not_none():
    v = classify(NAME, PHONE, "", ["https://unknownbrand.com"], True, client({"https://unknownbrand.com": "<h1>Hello world</h1>"}))
    assert v.status == "probable_site" and v.url == "https://unknownbrand.com"
    assert classify(NAME, PHONE, "", ["https://down.example"], True, client({})).status == "probable_site"


def test_domain_guess_verified_by_phone_number():
    v = classify(NAME, PHONE, "", [], True, client({"https://glow.com": "<p>Reach us on 011 2345 6789</p>"}))
    assert v.status == "has_site" and "domain guess" in v.evidence and "phone number" in v.evidence


def test_unverified_domain_guess_does_not_count():
    v = classify(NAME, PHONE, "", [], True, client({"https://glow.com": "<h1>Glow</h1><p>A different business</p>"}))  # shares one word with the name, no phone
    assert v.status == "none"


def test_unread_details_stay_unknown():
    assert classify(NAME, PHONE, "", [], False, client({})).status == "unknown"


def test_verify_websites_stage_updates_pending_leads(client_api=None):
    from fastapi.testclient import TestClient

    from app.main import app
    api = TestClient(app)
    rows = [{"name": NAME, "category_address": "Skin clinic · Saket", "phone": PHONE, "detail_read": True},
            {"name": "Plain Clinic", "category_address": "Skin clinic · Saket", "phone": "011 9999 8888", "detail_read": True,
             "links": ["https://plainclinic.example/"]},
            {"name": "Never Opened Clinic", "category_address": "Skin clinic · Saket"}]
    api.post("/leads/ingest", json={"rows": rows, "query": "skin clinic in saket"})
    stage_base.HTTP_TRANSPORT = make_transport({"https://glow.com": f"<p>{PHONE}</p>", "https://plainclinic.example": "<p>x</p>"})
    jid = create_job("verify_websites", None, None, False)
    assert run_job(jid) == "succeeded"
    from app.core.db import SessionLocal
    with SessionLocal() as s:
        by = {c.name: c.extra for c in s.scalars(select(Company).where(Company.source == "maps"))}
    assert by[NAME]["website_status"] == "has_site" and by[NAME]["website_url"] == "https://glow.com"
    assert by["Plain Clinic"]["website_status"] == "probable_site"
    assert by["Never Opened Clinic"]["website_status"] == "unknown"
    assert api.get("/leads", params={"site": "none"}).json()["total"] == 0
